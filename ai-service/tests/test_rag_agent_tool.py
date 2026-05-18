import json
import unittest
from unittest.mock import patch

from src.tools.picture_search import search_pictures_by_semantic


class AgentSemanticSearchToolTest(unittest.TestCase):
    def test_agent_semantic_search_skips_rag_answer_generation(self):
        calls = {}

        def fake_rag_semantic_search(query, space_id, top_k=10, *, generate_answer):
            calls["generate_answer"] = generate_answer
            return {
                "pictures": [
                    {
                        "picture_id": 1,
                        "picture_name": "红色赛车",
                        "url": "https://example.com/car.jpg",
                        "description": "红色赛车在赛道上行驶",
                        "score": 0.9,
                    }
                ],
                "answer": "",
            }

        with patch("src.tools.picture_search.rag_semantic_search", fake_rag_semantic_search):
            raw = search_pictures_by_semantic.invoke(
                {"query": "红色赛车", "space_id": 2019703681948540929, "top_k": 5}
            )

        self.assertFalse(raw.startswith("语义搜索失败"), raw)
        result = json.loads(raw)
        self.assertEqual(result[0]["id"], 1)
        self.assertFalse(calls["generate_answer"])

    def test_agent_semantic_search_keeps_missing_url_empty(self):
        def fake_rag_semantic_search(query, space_id, top_k=10, *, generate_answer):
            return {
                "pictures": [
                    {
                        "picture_id": 1,
                        "picture_name": "红色赛车",
                        "url": "",
                        "description": "红色赛车在赛道上行驶",
                        "score": 0.9,
                    }
                ],
                "answer": "",
            }

        with patch("src.tools.picture_search.rag_semantic_search", fake_rag_semantic_search):
            raw = search_pictures_by_semantic.invoke(
                {"query": "红色赛车", "space_id": 2019703681948540929, "top_k": 5}
            )

        result = json.loads(raw)
        self.assertEqual("", result[0]["url"])
        self.assertNotIn("originalUrl", result[0])

    def test_agent_semantic_search_merges_database_results_and_dedupes(self):
        def fake_rag_semantic_search(query, space_id, top_k=10, *, generate_answer):
            return {
                "pictures": [
                    {
                        "picture_id": 1,
                        "picture_name": "语义红色赛车",
                        "url": "https://example.com/semantic-1.jpg",
                        "description": "红色赛车在赛道上行驶",
                        "score": 0.9,
                    },
                    {
                        "picture_id": 2,
                        "picture_name": "重复赛车",
                        "url": "",
                        "description": "语义召回但缺少 URL",
                        "score": 0.8,
                    },
                ],
                "answer": "",
            }

        class FakeResponse:
            status_code = 200
            text = '{"code":0}'

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": {
                        "records": [
                            {
                                "id": 2,
                                "name": "重复赛车",
                                "url": "https://example.com/db-2.jpg",
                                "introduction": "数据库关键词命中",
                            },
                            {
                                "id": 3,
                                "name": "数据库赛车",
                                "url": "https://example.com/db-3.jpg",
                                "introduction": "只在数据库中命中",
                            },
                        ],
                        "total": 3,
                        "pages": 1,
                    }
                }

        with patch("src.tools.picture_search.rag_semantic_search", fake_rag_semantic_search), \
                patch("src.tools.picture_search.httpx.post", return_value=FakeResponse()) as post:
            raw = search_pictures_by_semantic.invoke({
                "query": "红色赛车",
                "space_id": 2019703681948540929,
                "top_k": 5,
                "user_id": 7,
            })

        self.assertGreaterEqual(post.call_count, 1)
        result = json.loads(raw)
        self.assertEqual([1, 2, 3], [item["id"] for item in result])
        self.assertEqual("https://example.com/db-2.jpg", result[1]["url"])

    def test_agent_semantic_search_splits_database_keyword_queries(self):
        def fake_rag_semantic_search(query, space_id, top_k=10, *, generate_answer):
            return {"pictures": [], "answer": ""}

        class FakeResponse:
            status_code = 200
            text = '{"code":0}'

            def __init__(self, request_json):
                self.request_json = request_json

            def raise_for_status(self):
                return None

            def json(self):
                if self.request_json.get("searchText") == "赛车":
                    return {
                        "data": {
                            "records": [
                                {
                                    "id": 10,
                                    "name": "经典赛车展示",
                                    "url": "https://example.com/classic.jpg",
                                    "introduction": "数据库关键词命中",
                                }
                            ],
                            "total": 1,
                            "pages": 1,
                        }
                    }
                return {"data": {"records": [], "total": 0, "pages": 0}}

        requests = []

        def fake_post(url, json, headers, timeout):
            requests.append(json)
            return FakeResponse(json)

        with patch("src.tools.picture_search.rag_semantic_search", fake_rag_semantic_search), \
                patch("src.tools.picture_search.httpx.post", side_effect=fake_post):
            raw = search_pictures_by_semantic.invoke({
                "query": "赛车 跑车 racing car",
                "space_id": 2019703681948540929,
                "top_k": 10,
                "user_id": 7,
            })

        search_texts = [request["searchText"] for request in requests]
        self.assertIn("赛车 跑车 racing car", search_texts)
        self.assertIn("赛车", search_texts)
        result = json.loads(raw)
        self.assertEqual([10], [item["id"] for item in result])

    def test_agent_semantic_search_filters_deleted_rag_results_with_java_detail(self):
        def fake_rag_semantic_search(query, space_id, top_k=10, *, generate_answer):
            return {
                "pictures": [
                    {
                        "picture_id": 1,
                        "picture_name": "已删除赛车",
                        "url": "https://example.com/deleted.jpg",
                        "description": "旧索引中的图片",
                        "score": 0.95,
                    },
                    {
                        "picture_id": 2,
                        "picture_name": "当前赛车",
                        "url": "https://example.com/stale-url.jpg",
                        "description": "仍存在的图片",
                        "score": 0.9,
                    },
                ],
                "answer": "",
            }

        class DetailResponse:
            status_code = 200

            def __init__(self, payload):
                self._payload = payload
                self.text = json.dumps(payload, ensure_ascii=False)

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class ListResponse:
            status_code = 200
            text = '{"code":0}'

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": {"records": [], "total": 0, "pages": 0}}

        def fake_get(url, params, headers, timeout):
            if params["id"] == 1:
                return DetailResponse({"code": 404, "message": "图片不存在", "data": None})
            return DetailResponse({
                "code": 0,
                "data": {
                    "id": 2,
                    "name": "当前赛车",
                    "thumbnailUrl": "https://example.com/live-thumb.jpg",
                    "url": "https://example.com/live.jpg",
                    "introduction": "Java 当前数据",
                    "tags": ["汽车", "运动"],
                },
            })

        with patch("src.tools.picture_search.rag_semantic_search", fake_rag_semantic_search), \
                patch("src.tools.picture_search.httpx.get", side_effect=fake_get), \
                patch("src.tools.picture_search.httpx.post", return_value=ListResponse()):
            raw = search_pictures_by_semantic.invoke({
                "query": "赛车",
                "space_id": 2019703681948540929,
                "top_k": 5,
                "user_id": 7,
            })

        result = json.loads(raw)
        self.assertEqual([2], [item["id"] for item in result])
        self.assertEqual("https://example.com/live-thumb.jpg", result[0]["url"])
        self.assertEqual("Java 当前数据", result[0]["description"])


if __name__ == "__main__":
    unittest.main()
