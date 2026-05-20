import json
import unittest

from src.core.tool_context import summarize_tool_result


class ToolContextTest(unittest.TestCase):
    def test_summarize_search_result_keeps_rank_and_ids(self):
        raw = json.dumps([
            {"id": 11, "name": "红色赛车", "url": "https://x/1.jpg", "score": 0.91},
            {"id": 12, "name": "黑色赛车", "url": "https://x/2.jpg", "score": 0.82},
        ], ensure_ascii=False)

        summary = summarize_tool_result("search_pictures_by_semantic", raw)

        self.assertEqual(11, summary["last_search_results"][0]["id"])
        self.assertEqual(2, summary["last_search_results"][1]["rank"])

    def test_summarize_search_result_empty_list(self):
        summary = summarize_tool_result("search_pictures_by_semantic", "[]")
        self.assertEqual([], summary["last_search_results"])

    def test_summarize_non_search_tool_returns_empty(self):
        summary = summarize_tool_result("analyze_space", "分析结果：10张图片")
        self.assertEqual({}, summary)

    def test_summarize_search_result_invalid_json(self):
        summary = summarize_tool_result("search_pictures_by_semantic", "未找到匹配的图片。")
        self.assertEqual([], summary["last_search_results"])
        self.assertIn("raw", summary)

    def test_summarize_search_result_preserves_all_fields(self):
        raw = json.dumps([
            {"id": 5, "name": "日落", "url": "https://x/5.jpg", "description": "美丽的日落", "score": 0.95},
        ], ensure_ascii=False)
        summary = summarize_tool_result("search_pictures_by_semantic", raw)
        item = summary["last_search_results"][0]
        self.assertEqual(1, item["rank"])
        self.assertEqual(5, item["id"])
        self.assertEqual("日落", item["name"])
        self.assertEqual("https://x/5.jpg", item["url"])
        self.assertAlmostEqual(0.95, item["score"])

    def test_summarize_tag_search_produces_last_search_results(self):
        raw = json.dumps([
            {"id": 101, "name": "赛车A", "url": "https://x/a.jpg", "score": 1.0},
            {"id": 102, "name": "赛车B", "url": "https://x/b.jpg", "score": 1.0},
        ], ensure_ascii=False)

        summary = summarize_tool_result("search_pictures_by_tag", raw)

        self.assertIn("last_search_results", summary)
        self.assertEqual(2, len(summary["last_search_results"]))
        self.assertEqual(101, summary["last_search_results"][0]["id"])
        self.assertEqual(2, summary["last_search_results"][1]["rank"])

    def test_summarize_edit_picture_returns_empty(self):
        summary = summarize_tool_result("edit_picture", "成功编辑 2/2 张图片。")
        self.assertEqual({}, summary)


if __name__ == "__main__":
    unittest.main()
