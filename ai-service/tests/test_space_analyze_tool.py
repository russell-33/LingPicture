import unittest
from unittest.mock import patch

from src.service.expert_analyst import ANALYST_TOOL_NAMES
from src.service.prompt import ANALYST_SYSTEM_PROMPT, SPACE_ANALYZE_PROMPT
from src.tools.space_analyze import analyze_space


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class SpaceAnalyzeToolTest(unittest.TestCase):
    def test_business_error_is_returned_without_llm_summary(self):
        responses = [
            FakeResponse({"code": 40100, "data": None, "msg": "内部用户不存在"}),
        ]

        with patch("src.tools.space_analyze.httpx.post", side_effect=responses), \
                patch("src.tools.space_analyze.chat") as chat:
            result = analyze_space.invoke({"space_id": 2019703681948540929, "user_id": 7})

        self.assertIn("空间分析失败", result)
        self.assertIn("内部用户不存在", result)
        chat.assert_not_called()

    def test_inconsistent_space_counter_is_reported_from_space_table(self):
        responses = [
            FakeResponse({
                "code": 0,
                "data": {
                    "usedCount": 0,
                    "usedSize": 0,
                    "maxCount": 1000,
                    "maxSize": 104857600,
                },
                "msg": "ok",
            }),
            FakeResponse({"code": 0, "data": [{"category": "素材", "count": 3, "totalSize": 4096}], "msg": "ok"}),
            FakeResponse({"code": 0, "data": [{"tag": "赛车", "count": 3}], "msg": "ok"}),
        ]

        with patch("src.tools.space_analyze.httpx.post", side_effect=responses), \
                patch("src.tools.space_analyze.chat") as chat:
            result = analyze_space.invoke({"space_id": 2019703681948540929, "user_id": 7})

        self.assertIn("space 表", result)
        self.assertIn("usedCount=0", result)
        self.assertIn("聚合字段", result)
        chat.assert_not_called()

    def test_space_analyze_prompt_respects_fixed_category_options(self):
        prompt_text = "\n".join(message.prompt.template for message in SPACE_ANALYZE_PROMPT.messages)

        self.assertIn("模板、电商、表情包、素材、海报、其他", prompt_text)
        self.assertIn("严禁建议用户“新建分类”", prompt_text)
        self.assertIn("不要建议新建分类", ANALYST_SYSTEM_PROMPT)
        self.assertNotIn("get_picture_detail", ANALYST_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
