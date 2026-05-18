import unittest
from unittest.mock import patch

from src.core.tool import TOOLS
from src.router import agent as agent_router
from src.service.expert_searcher import SEARCHER_TOOL_NAMES
from src.service.prompt import SEARCHER_SYSTEM_PROMPT


class AgentRouterMultiAgentTest(unittest.TestCase):
    def test_main_routes_use_multi_agent(self):
        paths = {route.path for route in agent_router.router.routes}

        self.assertIn("/agent/run", paths)
        self.assertIn("/agent/run/stream", paths)
        self.assertNotIn("/agent/run/legacy", paths)
        self.assertNotIn("/agent/run/stream/legacy", paths)

        request = agent_router.AgentRunRequest(
            task="帮我找红色赛车图片",
            session_id="session-1",
            space_id="201",
            user_id=7,
            max_steps=3,
        )

        with patch.object(agent_router, "run_multi_agent", return_value={"answer": "multi", "steps": 2}) as multi:
            response = agent_router.agent_run(request)

        multi.assert_called_once_with("帮我找红色赛车图片", "session-1", "201", 3, 7)
        self.assertEqual({"answer": "multi", "steps": 2, "session_id": "session-1"}, response)

    def test_searcher_agent_only_references_registered_tools(self):
        registered_tool_names = {tool.name for tool in TOOLS}

        self.assertTrue(SEARCHER_TOOL_NAMES <= registered_tool_names)
        self.assertNotIn("search_pictures_by_db", SEARCHER_SYSTEM_PROMPT)

    def test_messages_falls_back_to_redis_summary_when_message_cache_expired(self):
        with patch.object(agent_router, "load_messages", return_value=[]), \
                patch.object(agent_router, "load_summary", return_value="用户之前搜索过红色赛车图片"), \
                patch.object(agent_router, "load_durable_session_summary") as durable:
            response = agent_router.get_messages("session-1", user_id=7)

        durable.assert_not_called()
        self.assertEqual(1, len(response["messages"]))
        self.assertEqual("assistant", response["messages"][0]["role"])
        self.assertIn("用户之前搜索过红色赛车图片", response["messages"][0]["content"])

    def test_messages_falls_back_to_mysql_summary_and_warms_redis(self):
        with patch.object(agent_router, "load_messages", return_value=[]), \
                patch.object(agent_router, "load_summary", return_value=""), \
                patch.object(agent_router, "load_durable_session_summary", return_value="MySQL 中的长期摘要") as durable, \
                patch.object(agent_router, "save_summary") as save:
            response = agent_router.get_messages("session-1", user_id=7)

        durable.assert_called_once_with("session-1", 7)
        save.assert_called_once_with("session-1", "MySQL 中的长期摘要")
        self.assertEqual(1, len(response["messages"]))
        self.assertIn("MySQL 中的长期摘要", response["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
