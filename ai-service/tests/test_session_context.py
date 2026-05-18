import unittest
from unittest.mock import patch

from src.core.session_context import build_agent_messages


class SessionContextTest(unittest.TestCase):
    @patch("src.core.session_context.load_tool_context", return_value={"last_search_results": [{"id": 2, "name": "赛车"}]})
    @patch("src.core.session_context.load_summary", return_value="用户喜欢红色赛车图")
    @patch("src.core.session_context.load_messages", return_value=[{"role": "user", "content": "上一轮找赛车"}])
    def test_build_agent_messages_contains_summary_tool_context_and_task(self, *_):
        messages = build_agent_messages("s1", "刚才第二张给我看看", "201", 7, max_tokens=8000)
        contents = "\n".join(m["content"] for m in messages)

        self.assertEqual("system", messages[0]["role"])
        self.assertIn("空间 ID 201", messages[0]["content"])
        self.assertIn("历史摘要", contents)
        self.assertIn("last_search_results", contents)
        self.assertIn("刚才第二张给我看看", contents)

    @patch("src.core.session_context.save_summary")
    @patch("src.core.session_context.load_durable_session_summary", return_value="MySQL 中恢复的长期摘要")
    @patch("src.core.session_context.load_tool_context", return_value={})
    @patch("src.core.session_context.load_summary", return_value="")
    @patch("src.core.session_context.load_messages", return_value=[])
    def test_build_agent_messages_falls_back_to_mysql_summary(self, _messages, _redis_summary, _tool, _mysql_summary, save_summary):
        messages = build_agent_messages("s1", "我们刚才在找什么图", "201", 7, max_tokens=8000)
        contents = "\n".join(m["content"] for m in messages)

        self.assertIn("MySQL 中恢复的长期摘要", contents)
        save_summary.assert_called_once_with("s1", "MySQL 中恢复的长期摘要")


if __name__ == "__main__":
    unittest.main()
