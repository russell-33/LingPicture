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


if __name__ == "__main__":
    unittest.main()
