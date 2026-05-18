from src.core.tag_utils import normalize_tag

ALLOWED_TAGS = [
    "抽象",
    "动物",
    "动漫",
    "卡通",
    "CGI",
    "网络朋克",
    "幻想",
    "游戏",
    "女性",
    "男性",
    "风景",
    "中世纪",
    "网红事物",
    "MMD",
    "音乐",
    "自然",
    "像素艺术",
    "放松",
    "复古",
    "科幻",
    "运动",
    "科技",
    "电视节目",
    "汽车",
    "未指定样式",
]

FALLBACK_TAG = "未指定样式"
MIN_AUTO_TAGS = 2
MAX_AUTO_TAGS = 4


def allowed_tag_text() -> str:
    return "、".join(ALLOWED_TAGS)


def normalize_allowed_tags(tags: list[str], max_count: int = MAX_AUTO_TAGS) -> list[str]:
    allowed_by_norm = {normalize_tag(tag): tag for tag in ALLOWED_TAGS}
    result = []
    seen = set()

    for raw_tag in tags or []:
        tag = allowed_by_norm.get(normalize_tag(raw_tag))
        if not tag or tag in seen:
            continue
        result.append(tag)
        seen.add(tag)
        if len(result) >= max_count:
            break

    return result or [FALLBACK_TAG]
