import json
import unittest
from unittest.mock import patch

from src.tools.picture_edit import edit_picture
from src.tools.picture_search import search_pictures_by_tag


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class PictureTagToolsTest(unittest.TestCase):
    def test_search_pictures_by_tag_matches_business_tags_case_insensitive(self):
        responses = [
            FakeResponse({
                "data": {
                    "records": [
                        {
                            "id": 1,
                            "name": "经典赛车展示",
                            "url": "https://example.com/1.webp",
                            "tags": ["车", "racing car", "Racing Car"],
                        },
                        {
                            "id": 2,
                            "name": "山景",
                            "url": "https://example.com/2.webp",
                            "tags": ["自然"],
                        },
                    ],
                    "total": 3,
                    "pages": 2,
                }
            }),
            FakeResponse({
                "data": {
                    "records": [
                        {
                            "id": 3,
                            "name": "赛车17号展示",
                            "url": "https://example.com/3.webp",
                            "tags": ["Racing Car", "赛车"],
                        }
                    ],
                    "total": 3,
                    "pages": 2,
                }
            }),
        ]

        with patch("src.tools.picture_search.httpx.post", side_effect=responses):
            raw = search_pictures_by_tag.invoke({
                "tag": "racing car",
                "space_id": 2019703681948540929,
                "user_id": 7,
            })

        result = json.loads(raw)
        self.assertEqual([1, 3], [item["id"] for item in result])

    def test_search_pictures_by_tag_matches_any_comma_separated_tag(self):
        responses = [
            FakeResponse({
                "data": {
                    "records": [
                        {
                            "id": 1,
                            "name": "经典赛车展示",
                            "url": "https://example.com/1.webp",
                            "tags": ["车", "Racing"],
                        },
                        {
                            "id": 2,
                            "name": "赛车17号展示",
                            "url": "https://example.com/2.webp",
                            "tags": ["Racing Car", "赛车"],
                        },
                        {
                            "id": 3,
                            "name": "山景",
                            "url": "https://example.com/3.webp",
                            "tags": ["自然"],
                        },
                    ],
                    "total": 3,
                    "pages": 1,
                }
            }),
        ]

        with patch("src.tools.picture_search.httpx.post", side_effect=responses):
            raw = search_pictures_by_tag.invoke({
                "tag": "Racing Car,Racing",
                "space_id": 2019703681948540929,
                "user_id": 7,
            })

        result = json.loads(raw)
        self.assertEqual([1, 2], [item["id"] for item in result])

    def test_edit_picture_removes_tags_case_insensitive(self):
        posted = {}

        def fake_post(url, json, headers, timeout):
            posted.update(json)
            return FakeResponse({"code": 0, "data": True, "msg": "ok"})

        detail = FakeResponse({
            "data": {
                "id": 1,
                "tags": ["Racing Car", "racing car", "赛车"],
            }
        })

        with patch("src.tools.picture_edit.httpx.get", return_value=detail), \
                patch("src.tools.picture_edit.httpx.post", side_effect=fake_post):
            result = edit_picture.invoke({
                "picture_ids": "1",
                "space_id": 2019703681948540929,
                "remove_tags": "racing car",
                "user_id": 7,
            })

        self.assertEqual("成功编辑 1/1 张图片。", result)
        self.assertEqual(["赛车"], posted["tags"])


if __name__ == "__main__":
    unittest.main()
