import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.service.expert_searcher import build_searcher_agent
from src.service.multi_agent import summarize_node


class SequencedCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="tool-call-1",
                    function=SimpleNamespace(
                        name="search_pictures_by_semantic",
                        arguments='{"query":"红色赛车","top_k":5}',
                    ),
                )
            ],
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class SequencedClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SequencedCompletions())


class MultiAgentSearchMarkdownTest(unittest.TestCase):
    def test_searcher_formats_tool_json_with_real_urls_without_llm_rewrite(self):
        raw_result = (
            '[{"id": 1, "name": "红色赛车疾驰", '
            '"url": "https://example.com/car-1.webp", "score": 0.91}, '
            '{"id": 2, "name": "F1赛车竞速", '
            '"url": "https://example.com/car-2.webp", "score": 0.88}]'
        )
        app = build_searcher_agent()
        state = {
            "messages": [],
            "task_description": "帮我找红色赛车相关的图片，5 张",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "session-1",
            "step_count": 0,
            "max_steps": 6,
        }
        client = SequencedClient()

        with patch("src.service.expert_common.get_llm_client", return_value=client), \
                patch("src.service.expert_common.execute_tool", return_value=raw_result):
            result = app.invoke(state)

        answer = result["messages"][-1]["content"]
        self.assertIn("![红色赛车疾驰](https://example.com/car-1.webp)", answer)
        self.assertIn("[查看详情](/picture/1)", answer)
        self.assertIn("![F1赛车竞速](https://example.com/car-2.webp)", answer)
        self.assertNotIn("![]()", answer)
        self.assertEqual(1, len(client.chat.completions.calls))

    def test_summarize_returns_single_searcher_markdown_result_directly(self):
        searcher_result = (
            "已找到相关图片：\n"
            "1. ![红色赛车疾驰](https://example.com/car-1.webp)  [查看详情](/picture/1)"
        )
        state = {
            "messages": [],
            "plan": [{
                "id": "1",
                "description": "搜索红色赛车图片",
                "agent": "searcher",
                "status": "done",
                "result": searcher_result,
            }],
        }

        with patch("src.service.multi_agent.get_llm_client") as client:
            result = summarize_node(state)

        self.assertEqual(searcher_result, result["final_answer"])
        client.assert_not_called()

    def test_summarize_returns_single_analyst_result_directly(self):
        analyst_result = "空间分析结果：当前空间共有 8 张图片，使用了 12.5MB 存储。"
        state = {
            "messages": [],
            "plan": [{
                "id": "1",
                "description": "分析当前空间",
                "agent": "analyst",
                "status": "done",
                "result": analyst_result,
            }],
        }

        with patch("src.service.multi_agent.get_llm_client") as client:
            result = summarize_node(state)

        self.assertEqual(analyst_result, result["final_answer"])
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
