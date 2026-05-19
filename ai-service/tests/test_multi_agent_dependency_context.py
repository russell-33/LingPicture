import unittest
from unittest.mock import patch

from src.service.multi_agent import _run_expert


class CapturingExpertApp:
    def __init__(self):
        self.received_state = None

    def invoke(self, state):
        self.received_state = state
        return {"messages": [{"role": "assistant", "content": "成功编辑 2/2 张图片。"}]}


class MultiAgentDependencyContextTest(unittest.TestCase):
    def test_editor_receives_prior_search_result_and_picture_ids(self):
        expert = CapturingExpertApp()
        state = {
            "plan": [
                {
                    "id": "1",
                    "description": "搜索带 racingcar 标签的赛车图片",
                    "agent": "searcher",
                    "status": "done",
                    "result": (
                        "已找到相关图片：\n"
                        "1. ![F1赛车疾驰](https://example.com/1.webp)  [查看详情](/picture/2052600060341587969)\n"
                        "2. ![赛车竞速](https://example.com/2.webp)  [查看详情](/picture/2052598748216516609)"
                    ),
                },
                {
                    "id": "2",
                    "description": "删除上述图片的 racingcar 标签",
                    "agent": "editor",
                    "status": "pending",
                    "result": "",
                },
            ],
            "current_subtask": "2",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "session-1",
        }

        _run_expert(expert, state)

        task_description = expert.received_state["task_description"]
        self.assertIn("上游已完成任务结果", task_description)
        self.assertIn("2052600060341587969,2052598748216516609", task_description)
        self.assertIn("删除上述图片的 racingcar 标签", task_description)

    def test_expert_reloads_latest_tool_context_before_building_task(self):
        expert = CapturingExpertApp()
        state = {
            "plan": [
                {
                    "id": "1",
                    "description": "搜索赛车图片",
                    "agent": "searcher",
                    "status": "done",
                    "result": "已找到相关图片。",
                },
                {
                    "id": "2",
                    "description": '为这些图片添加标签；使用 edit_picture(tags="赛车")',
                    "agent": "editor",
                    "status": "pending",
                    "result": "",
                },
            ],
            "current_task": "给这几张图片打上赛车标签",
            "current_subtask": "2",
            "tool_context": {
                "last_search_results": [
                    {"rank": 1, "id": 1111111111111111111, "name": "旧快照图片"},
                ],
            },
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "session-1",
        }
        fresh_context = {
            "last_search_results": [
                {"rank": 1, "id": 2056647696043470849, "name": "赛车停赛场"},
                {"rank": 2, "id": 2056707647105396738, "name": "赛车展示"},
            ],
        }

        with patch("src.core.memory.load_tool_context", return_value=fresh_context) as load_context:
            _run_expert(expert, state)

        load_context.assert_called_once_with("session-1")
        task_description = expert.received_state["task_description"]
        self.assertIn("2056647696043470849,2056707647105396738", task_description)
        self.assertNotIn("1111111111111111111", task_description)


if __name__ == "__main__":
    unittest.main()
