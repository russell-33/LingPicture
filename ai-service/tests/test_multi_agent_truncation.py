import json
import unittest
from unittest.mock import patch

from src.service.expert_common import make_execute_tools
from src.service.multi_agent import _update_plan_after_expert


class MultiAgentTruncationTest(unittest.TestCase):
    def test_supervisor_keeps_complete_expert_image_markdown(self):
        images = []
        for idx in range(1, 6):
            url = f"https://example.com/images/{'red-race-car-' * 12}{idx}.jpg"
            images.append(f"{idx}. ![红色赛车{idx}]({url})  [查看详情](/picture/{idx})")
        expert_result = "\n".join(images)
        plan = [{
            "id": "1",
            "description": "搜索红色赛车图片，返回 5 张",
            "agent": "searcher",
            "status": "pending",
            "result": "",
        }]

        updated = _update_plan_after_expert(plan, "1", "done", expert_result)

        self.assertEqual(expert_result, updated[0]["result"])
        self.assertIn("红色赛车5", updated[0]["result"])
        self.assertIn("/picture/5", updated[0]["result"])

    def test_search_tool_result_is_not_cut_in_the_middle_of_json_or_urls(self):
        long_records = []
        for idx in range(1, 6):
            long_records.append({
                "id": idx,
                "name": f"红色赛车{idx}",
                "url": f"https://example.com/{'very-long-path-' * 30}{idx}.jpg",
                "description": "红色赛车在赛道上高速行驶，观众在背景中。" * 12,
                "score": 0.9,
            })
        raw_tool_result = json.dumps(long_records, ensure_ascii=False)
        execute_tools = make_execute_tools({"search_pictures_by_semantic"})
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "search_pictures_by_semantic",
                        "arguments": json.dumps({"query": "红色赛车", "top_k": 5}, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": "帮我找红色赛车相关的图片，5 张",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 6,
        }

        with patch("src.service.expert_common.execute_tool", return_value=raw_tool_result):
            result = execute_tools(state)

        content = result["messages"][0]["content"]
        parsed = json.loads(content)
        self.assertEqual(5, len(parsed))
        self.assertEqual(5, parsed[-1]["id"])
        self.assertTrue(parsed[-1]["url"].endswith("5.jpg"))


if __name__ == "__main__":
    unittest.main()
