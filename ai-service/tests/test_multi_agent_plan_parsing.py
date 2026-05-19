import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.service.multi_agent import _generate_plan


class FencedPlanClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        content = """```json
[
    {
        "id": "1",
        "description": "搜索所有与赛车相关的图片",
        "agent": "searcher"
    },
    {
        "id": "2",
        "description": "利用上游搜索结果获取图片ID列表，批量删除这些图片的 racingcar 标签",
        "agent": "editor"
    }
]
```"""
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class AddTagPlanClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        content = """[
    {
        "id": "1",
        "description": "为这些图片添加标签",
        "agent": "editor"
    }
]"""
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class MultiAgentPlanParsingTest(unittest.TestCase):
    def test_generate_plan_parses_markdown_fenced_json_array(self):
        state = {"current_task": "删除有关赛车图片的 racingcar 标签"}

        with patch("src.service.multi_agent.get_llm_client", return_value=FencedPlanClient()):
            plan = _generate_plan(state)

        self.assertEqual(2, len(plan))
        self.assertEqual("searcher", plan[0]["agent"])
        self.assertEqual("editor", plan[1]["agent"])
        self.assertIn("remove_tags", plan[1]["description"])

    def test_generate_plan_keeps_multi_word_remove_tag(self):
        state = {"current_task": "删除有关赛车图片的 racing car 标签"}

        with patch("src.service.multi_agent.get_llm_client", return_value=FencedPlanClient()):
            plan = _generate_plan(state)

        self.assertIn("racing car", plan[0]["description"])
        self.assertIn('remove_tags="racing car"', plan[1]["description"])
        self.assertNotIn('remove_tags="car"', plan[1]["description"])

    def test_generate_plan_preserves_add_tag_value_for_editor(self):
        state = {
            "current_task": "给这几张图片打上赛车标签",
            "tool_context": {
                "last_search_results": [
                    {"rank": 1, "id": 2056647696043470849, "name": "赛车停赛场"},
                ],
            },
        }

        with patch("src.service.multi_agent.get_llm_client", return_value=AddTagPlanClient()):
            plan = _generate_plan(state)

        self.assertEqual("editor", plan[0]["agent"])
        self.assertIn('tags="赛车"', plan[0]["description"])


if __name__ == "__main__":
    unittest.main()
