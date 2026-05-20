import json
import unittest
from unittest.mock import patch

from src.core.tag_utils import extract_add_tag, extract_remove_tag, extract_remove_tags
from src.service.expert_common import make_agent_node, make_execute_tools


class MultiAgentEditorSafetyTest(unittest.TestCase):
    def test_extracts_multiple_quoted_remove_tags(self):
        text = "给有关赛车的图片删除“Racing Car”标签和“Racing”标签"

        self.assertEqual(["Racing Car", "Racing"], extract_remove_tags(text))
        self.assertEqual("Racing Car,Racing", extract_remove_tag(text))

    def test_extracts_explicit_add_tag_hint(self):
        text = '为这些图片添加标签；使用 edit_picture(tags="赛车")'

        self.assertEqual("赛车", extract_add_tag(text))

    def test_editor_directly_calls_edit_picture_for_upstream_ids_and_multiple_remove_tags(self):
        node = make_agent_node("你是图片编辑专家。", {"edit_picture", "get_picture_detail"})
        state = {
            "messages": [],
            "task_description": (
                "当前子任务：为上游返回的图片删除“Racing Car”标签和“Racing”标签\n"
                "从上游结果中提取到的 picture_ids：2052600060341587969,2052598748216516609"
            ),
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 0,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.get_llm_client") as client:
            result = node(state)

        client.assert_not_called()
        tool_call = result["messages"][0]["tool_calls"][0]
        self.assertEqual("edit_picture", tool_call["function"]["name"])
        args = json.loads(tool_call["function"]["arguments"])
        self.assertEqual("2052600060341587969,2052598748216516609", args["picture_ids"])
        self.assertEqual("Racing Car,Racing", args["remove_tags"])
        self.assertEqual("", args["tags"])

    def test_add_tag_task_fills_missing_tags_arg(self):
        execute_tools = make_execute_tools(
            {"edit_picture"},
            inject_user_id_tools={"edit_picture"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "edit_picture",
                        "arguments": json.dumps({
                            "picture_ids": "2052600060341587969,2052598748216516609",
                        }, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": (
                "当前子任务：给关于赛车的图加上赛车标签\n"
                "从上游结果中提取到的 picture_ids：2052600060341587969,2052598748216516609"
            ),
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="成功编辑 2/2 张图片。") as tool:
            execute_tools(state)

        args = tool.call_args.args[1]
        self.assertEqual("赛车", args["tags"])
        self.assertEqual("", args.get("remove_tags", ""))

    def test_add_tag_task_fills_missing_tags_from_explicit_hint(self):
        execute_tools = make_execute_tools(
            {"edit_picture"},
            inject_user_id_tools={"edit_picture"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "edit_picture",
                        "arguments": json.dumps({
                            "picture_ids": "2056647696043470849,2056707647105396738",
                        }, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": (
                "当前子任务：为这些图片添加标签；使用 edit_picture(tags=\"赛车\")\n"
                "根据当前用户指代解析出的 picture_ids：2056647696043470849,2056707647105396738"
            ),
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="成功编辑 2/2 张图片。") as tool:
            execute_tools(state)

        args = tool.call_args.args[1]
        self.assertEqual("赛车", args["tags"])
        self.assertEqual("", args.get("remove_tags", ""))

    def test_delete_tag_task_routes_semantic_search_to_exact_tag_search(self):
        execute_tools = make_execute_tools(
            {"search_pictures_by_semantic", "search_pictures_by_tag"},
            inject_user_id_tools={"search_pictures_by_tag"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "search_pictures_by_semantic",
                        "arguments": json.dumps({"query": "racing car 赛车"}, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": "按业务标签搜索当前空间中包含 \"racing car\" 标签的图片，删除有关赛车图片的 racing car 标签",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="[]") as tool:
            execute_tools(state)

        name, args = tool.call_args.args
        self.assertEqual("search_pictures_by_tag", name)
        self.assertEqual("racing car", args["tag"])
        self.assertEqual(2019703681948540929, args["space_id"])
        self.assertEqual(7, args["user_id"])

    def test_delete_multiple_tags_overrides_tag_search_argument(self):
        execute_tools = make_execute_tools(
            {"search_pictures_by_tag"},
            inject_user_id_tools={"search_pictures_by_tag"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "search_pictures_by_tag",
                        "arguments": json.dumps({"tag": "Racing Car"}, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": "给有关赛车的图片删除“Racing Car”标签和“Racing”标签",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="[]") as tool:
            execute_tools(state)

        name, args = tool.call_args.args
        self.assertEqual("search_pictures_by_tag", name)
        self.assertEqual("Racing Car,Racing", args["tag"])

    def test_add_tag_task_expands_semantic_search_limit(self):
        execute_tools = make_execute_tools(
            {"search_pictures_by_semantic"},
            inject_user_id_tools={"search_pictures_by_semantic"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "search_pictures_by_semantic",
                        "arguments": json.dumps({"query": "赛车 跑车 racing car", "top_k": 10}, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": "给关于赛车的图加上赛车标签",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="[]") as tool:
            execute_tools(state)

        name, args = tool.call_args.args
        self.assertEqual("search_pictures_by_semantic", name)
        self.assertEqual(50, args["top_k"])
        self.assertEqual(7, args["user_id"])


    def test_delete_tag_task_converts_mistaken_tags_arg_to_remove_tags(self):
        execute_tools = make_execute_tools(
            {"edit_picture"},
            inject_user_id_tools={"edit_picture"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "edit_picture",
                        "arguments": json.dumps({
                            "picture_ids": "2052600060341587969,2052598748216516609",
                            "tags": "racingcar",
                        }, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": (
                "当前子任务：删除这些图片的 racingcar 标签\n"
                "从上游结果中提取到的 picture_ids：2052600060341587969,2052598748216516609"
            ),
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="成功编辑 2/2 张图片。") as tool:
            execute_tools(state)

        args = tool.call_args.args[1]
        self.assertEqual("", args["tags"])
        self.assertEqual("racingcar", args["remove_tags"])

    def test_delete_tag_task_keeps_multi_word_remove_tag(self):
        execute_tools = make_execute_tools(
            {"edit_picture"},
            inject_user_id_tools={"edit_picture"},
        )
        state = {
            "messages": [{
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "edit_picture",
                        "arguments": json.dumps({
                            "picture_ids": "2052600060341587969",
                            "tags": "racing car",
                        }, ensure_ascii=False),
                    },
                }],
            }],
            "task_description": (
                "当前子任务：删除有关赛车图片的 racing car 标签\n"
                "从上游结果中提取到的 picture_ids：2052600060341587969"
            ),
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "",
            "step_count": 1,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.execute_tool", return_value="成功编辑 1/1 张图片。") as tool:
            execute_tools(state)

        args = tool.call_args.args[1]
        self.assertEqual("", args["tags"])
        self.assertEqual("racing car", args["remove_tags"])


if __name__ == "__main__":
    unittest.main()
