import unittest
from unittest.mock import patch
from types import SimpleNamespace

from src.service.expert_common import build_expert_graph, make_agent_node


class FakeMessage:
    content = ""
    tool_calls = None


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self):
        self.chat = FakeChat()


class SequencedCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            message = SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="tool-call-1",
                        function=SimpleNamespace(name="analyze_space", arguments="{}"),
                    )
                ],
            )
        else:
            message = SimpleNamespace(content="总结完成", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class SequencedClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SequencedCompletions())


class MultiToolCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        call_index = len(self.calls)
        if call_index == 1:
            message = SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="tool-call-detail",
                        function=SimpleNamespace(
                            name="get_picture_detail",
                            arguments='{"picture_id": 2056647624081797122}',
                        ),
                    )
                ],
            )
        elif call_index == 2:
            message = SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="tool-call-edit",
                        function=SimpleNamespace(
                            name="edit_picture",
                            arguments='{"picture_ids": "2056647624081797122", "tags": "F1"}',
                        ),
                    )
                ],
            )
        else:
            message = SimpleNamespace(content="已成功添加标签。", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class MultiToolClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=MultiToolCompletions())


class MultiAgentExpertContextTest(unittest.TestCase):
    def test_expert_llm_receives_trusted_space_context(self):
        client = FakeClient()
        node = make_agent_node("你是数据分析专家。", {"analyze_space"})
        state = {
            "messages": [],
            "task_description": "分析一下我的空间的使用情况",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "session-1",
            "step_count": 0,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.get_llm_client", return_value=client):
            node(state)

        messages = client.chat.completions.calls[0]["messages"]
        user_message = messages[-1]["content"]
        self.assertIn("当前可信空间 ID: 2019703681948540929", user_message)
        self.assertIn("不要向用户索要空间 ID", user_message)

    def test_expert_summarizes_tool_result_without_resending_tool_protocol(self):
        client = SequencedClient()
        app = build_expert_graph(
            prefix="analyst_test",
            system_prompt="你是数据分析专家。",
            tool_names={"analyze_space"},
            inject_user_id_tools={"analyze_space"},
            summary_instruction="请总结分析结果。",
        )
        state = {
            "messages": [],
            "task_description": "分析一下我的空间的使用情况",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "session-1",
            "step_count": 0,
            "max_steps": 4,
        }

        with patch("src.service.expert_common.get_llm_client", return_value=client), \
                patch("src.service.expert_common.execute_tool", return_value="空间共有 10 张图片。"):
            result = app.invoke(state)

        self.assertEqual(2, len(client.chat.completions.calls))
        respond_messages = client.chat.completions.calls[1]["messages"]
        for message in respond_messages:
            self.assertNotEqual("tool", message.get("role"))
            self.assertNotIn("tool_calls", message)
            self.assertNotIn("tool_call_id", message)
        self.assertIn("空间共有 10 张图片。", respond_messages[-1]["content"])
        self.assertEqual("总结完成", result["messages"][-1]["content"])

    def test_expert_can_continue_with_second_tool_after_detail_lookup(self):
        client = MultiToolClient()
        app = build_expert_graph(
            prefix="editor_test",
            system_prompt="你是图片编辑专家。",
            tool_names={"get_picture_detail", "edit_picture"},
            inject_user_id_tools={"get_picture_detail", "edit_picture"},
            summary_instruction="请总结编辑结果。",
        )
        state = {
            "messages": [],
            "task_description": "给第一张图打上 F1 标签",
            "space_id": "2019703681948540929",
            "user_id": 7,
            "session_id": "session-1",
            "step_count": 0,
            "max_steps": 4,
        }

        executed_tools = []

        def fake_execute_tool(name, args):
            executed_tools.append((name, args))
            if name == "get_picture_detail":
                return '{"id":2056647624081797122,"name":"红色赛车展示","tags":["科技","运动"]}'
            return "成功编辑 1/1 张图片。"

        with patch("src.service.expert_common.get_llm_client", return_value=client), \
                patch("src.service.expert_common.execute_tool", side_effect=fake_execute_tool):
            result = app.invoke(state)

        self.assertEqual(["get_picture_detail", "edit_picture"], [name for name, _ in executed_tools])
        self.assertEqual(3, len(client.chat.completions.calls))
        self.assertEqual("已成功添加标签。", result["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
