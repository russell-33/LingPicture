import unittest

from src.core import memory


class MemoryContextTest(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_context_session"
        memory.clear_messages(self.session_id)
        memory.clear_tool_context(self.session_id)

    def test_summary_round_trip(self):
        memory.save_summary(self.session_id, "用户正在找红色赛车图")
        self.assertEqual("用户正在找红色赛车图", memory.load_summary(self.session_id))

    def test_tool_context_round_trip(self):
        context = {"last_search_results": [{"id": 1, "name": "红色赛车"}]}
        memory.save_tool_context(self.session_id, context)
        self.assertEqual(context, memory.load_tool_context(self.session_id))


if __name__ == "__main__":
    unittest.main()
