import unittest
from unittest.mock import patch

from src.core.compact import should_compact, build_compact_prompt


class CompactTest(unittest.TestCase):
    @patch("src.core.compact.count_message_tokens", return_value=7000)
    def test_should_compact_when_threshold_exceeded(self, _):
        self.assertTrue(should_compact([{"role": "user", "content": "x"}], threshold_tokens=6000))

    @patch("src.core.compact.count_message_tokens", return_value=1000)
    def test_should_not_compact_when_under_threshold(self, _):
        self.assertFalse(should_compact([{"role": "user", "content": "x"}], threshold_tokens=6000))

    def test_build_compact_prompt_returns_two_messages(self):
        messages = [
            {"role": "user", "content": "帮我找红色赛车"},
            {"role": "assistant", "content": "找到了3张"},
        ]
        prompt = build_compact_prompt(messages)
        self.assertEqual(2, len(prompt))
        self.assertEqual("system", prompt[0]["role"])
        self.assertIn("摘要", prompt[0]["content"])
        self.assertEqual("user", prompt[1]["role"])


if __name__ == "__main__":
    unittest.main()
