import json
import unittest

from src.core.tool_context import summarize_tool_result, append_search_round, get_all_search_results


class ToolContextTest(unittest.TestCase):
    def test_summarize_search_result_keeps_rank_and_ids(self):
        raw = json.dumps([
            {"id": 11, "name": "红色赛车", "url": "https://x/1.jpg", "score": 0.91},
            {"id": 12, "name": "黑色赛车", "url": "https://x/2.jpg", "score": 0.82},
        ], ensure_ascii=False)

        results = summarize_tool_result("search_pictures_by_semantic", raw)

        self.assertEqual(11, results[0]["id"])
        self.assertEqual(2, results[1]["rank"])

    def test_summarize_search_result_empty_list(self):
        results = summarize_tool_result("search_pictures_by_semantic", "[]")
        self.assertEqual([], results)

    def test_summarize_non_search_tool_returns_empty(self):
        results = summarize_tool_result("analyze_space", "分析结果：10张图片")
        self.assertEqual([], results)

    def test_summarize_search_result_invalid_json(self):
        results = summarize_tool_result("search_pictures_by_semantic", "未找到匹配的图片。")
        self.assertEqual([], results)

    def test_summarize_search_result_preserves_all_fields(self):
        raw = json.dumps([
            {"id": 5, "name": "日落", "url": "https://x/5.jpg", "description": "美丽的日落", "score": 0.95},
        ], ensure_ascii=False)
        results = summarize_tool_result("search_pictures_by_semantic", raw)
        item = results[0]
        self.assertEqual(1, item["rank"])
        self.assertEqual(5, item["id"])
        self.assertEqual("日落", item["name"])
        self.assertEqual("https://x/5.jpg", item["url"])
        self.assertAlmostEqual(0.95, item["score"])

    def test_summarize_tag_search_produces_list(self):
        raw = json.dumps([
            {"id": 101, "name": "赛车A", "url": "https://x/a.jpg", "score": 1.0},
            {"id": 102, "name": "赛车B", "url": "https://x/b.jpg", "score": 1.0},
        ], ensure_ascii=False)

        results = summarize_tool_result("search_pictures_by_tag", raw)

        self.assertEqual(2, len(results))
        self.assertEqual(101, results[0]["id"])
        self.assertEqual(2, results[1]["rank"])

    def test_summarize_edit_picture_returns_empty(self):
        results = summarize_tool_result("edit_picture", "成功编辑 2/2 张图片。")
        self.assertEqual([], results)


class AppendSearchRoundTest(unittest.TestCase):
    def test_append_creates_search_rounds(self):
        ctx = {}
        results = [{"id": 1, "name": "a"}]
        updated = append_search_round(ctx, results, "query1")

        self.assertEqual(results, updated["last_search_results"])
        self.assertEqual(1, len(updated["search_rounds"]))
        self.assertEqual(results, updated["search_rounds"][0]["results"])
        self.assertEqual("query1", updated["search_rounds"][0]["query"])

    def test_append_accumulates_rounds(self):
        ctx = {}
        ctx = append_search_round(ctx, [{"id": 1}], "q1")
        ctx = append_search_round(ctx, [{"id": 2}], "q2")
        ctx = append_search_round(ctx, [{"id": 3}], "q3")

        self.assertEqual(3, len(ctx["search_rounds"]))
        self.assertEqual([{"id": 3}], ctx["last_search_results"])

    def test_append_caps_at_max_rounds(self):
        ctx = {}
        for i in range(8):
            ctx = append_search_round(ctx, [{"id": i}], f"q{i}")

        self.assertEqual(5, len(ctx["search_rounds"]))
        # 最早的 3 轮被丢弃，保留 id=3..7
        self.assertEqual(3, ctx["search_rounds"][0]["results"][0]["id"])


class GetAllSearchResultsTest(unittest.TestCase):
    def test_returns_deduplicated_results_newest_first(self):
        ctx = {}
        ctx = append_search_round(ctx, [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], "q1")
        ctx = append_search_round(ctx, [{"id": 2, "name": "b"}, {"id": 3, "name": "c"}], "q2")

        all_results = get_all_search_results(ctx)

        ids = [r["id"] for r in all_results]
        self.assertEqual([2, 3, 1], ids)  # 新轮优先，去重

    def test_falls_back_to_last_search_results(self):
        ctx = {"last_search_results": [{"id": 5}]}
        all_results = get_all_search_results(ctx)
        self.assertEqual([{"id": 5}], all_results)

    def test_empty_context_returns_empty(self):
        self.assertEqual([], get_all_search_results({}))


if __name__ == "__main__":
    unittest.main()
