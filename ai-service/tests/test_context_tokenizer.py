import unittest
from unittest.mock import patch

from src.core import context


class FakeQwenTokenizer:
    def __init__(self, token_counts):
        self.token_counts = token_counts
        self.encoded = []

    def encode(self, text, add_special_tokens=False):
        self.encoded.append((text, add_special_tokens))
        return list(range(self.token_counts.get(text, len(text))))

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        return "\n".join(f"{msg['role']}:{msg['content']}" for msg in messages)


class ContextTokenizerTest(unittest.TestCase):
    def test_count_tokens_uses_qwen_tokenizer(self):
        tokenizer = FakeQwenTokenizer({"你好，Qwen": 3})

        with patch("src.core.context._get_qwen_tokenizer", return_value=tokenizer):
            self.assertEqual(context.count_tokens("你好，Qwen"), 3)

        self.assertEqual(tokenizer.encoded, [("你好，Qwen", False)])

    def test_slide_window_uses_qwen_message_counts(self):
        tokenizer = FakeQwenTokenizer({
            "system:system prompt": 5,
            "user:old message": 12,
            "assistant:new answer": 4,
            "user:new question": 4,
        })
        messages = [
            {"role": "user", "content": "old message"},
            {"role": "assistant", "content": "new answer"},
            {"role": "user", "content": "new question"},
        ]

        with patch("src.core.context._get_qwen_tokenizer", return_value=tokenizer):
            result = context.slide_window(messages, "system prompt", max_tokens=17)

        self.assertEqual([
            {"role": "system", "content": "system prompt"},
            {"role": "assistant", "content": "new answer"},
            {"role": "user", "content": "new question"},
        ], result)


if __name__ == "__main__":
    unittest.main()
