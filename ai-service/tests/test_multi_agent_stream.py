import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.service.multi_agent import run_multi_agent_stream


class FakeMultiAgentApp:
    async def astream_events(self, _state, version=None, config=None):
        yield {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": SimpleNamespace(content="当前分析任务已准备就绪，但系统暂未收到您的空间 ID。")
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {
                "output": {
                    "final_answer": "空间分析完成：共有 10 张图片。",
                    "supervisor_round": 2,
                    "plan": [],
                }
            },
        }


class MultiAgentStreamTest(unittest.TestCase):
    def test_stream_does_not_leak_internal_llm_chunks(self):
        async def collect():
            with patch("src.service.multi_agent.multi_agent_app", FakeMultiAgentApp()), \
                    patch("src.core.session_context.build_agent_messages", return_value=[]), \
                    patch("src.service.multi_agent._save_messages"):
                return [
                    chunk async for chunk in run_multi_agent_stream(
                        "分析一下我的空间的使用情况",
                        "session-1",
                        "2019703681948540929",
                        6,
                        7,
                    )
                ]

        chunks = asyncio.run(collect())
        payloads = [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

        self.assertNotIn("当前分析任务已准备就绪", "".join(chunk for chunk in chunks))
        self.assertEqual({"type": "reasoning", "content": "空间分析完成：共有 10 张图片。"}, payloads[0])
        self.assertEqual({"type": "final", "answer": "空间分析完成：共有 10 张图片。", "steps": 2}, payloads[-1])


if __name__ == "__main__":
    unittest.main()
