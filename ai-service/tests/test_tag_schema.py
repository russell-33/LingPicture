import unittest

from src.core.tag_schema import FALLBACK_TAG, normalize_allowed_tags


class TagSchemaTest(unittest.TestCase):
    def test_normalize_allowed_tags_filters_dedupes_and_limits(self):
        tags = normalize_allowed_tags(["汽车", "赛车", "运动", "汽车", "科技", "自然", "红色"])

        self.assertEqual(["汽车", "运动", "科技", "自然"], tags)

    def test_normalize_allowed_tags_falls_back_when_no_allowed_tag(self):
        tags = normalize_allowed_tags(["赛车", "红色"])

        self.assertEqual([FALLBACK_TAG], tags)


if __name__ == "__main__":
    unittest.main()
