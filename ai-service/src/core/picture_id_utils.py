import re
from typing import Optional

ORDINAL_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def extract_picture_ids_from_text(text: str) -> list[str]:
    """从任意文本中提取图片 ID，保序去重。

    优先匹配结构化格式（marker、URL、JSON），最后回退到裸数字。
    """
    content = str(text or "")
    ids = []
    seen = set()

    def _add(match: str) -> None:
        if match and match not in seen:
            seen.add(match)
            ids.append(match)

    # 1. marker 格式：picture_ids：123,456,789
    marker_match = re.search(r"picture_ids[：:]\s*([0-9,\s]+)", content)
    if marker_match:
        for num in re.findall(r"\d{8,}", marker_match.group(1)):
            _add(num)
        if ids:
            return ids

    # 2. 结构化格式
    for pattern in [
        r"/picture/(\d+)",
        r'"id"\s*:\s*"?(\d+)"?',
        r'"picture_id"\s*:\s*"?(\d+)"?',
        r"ID[:：]\s*(\d+)",
    ]:
        for match in re.findall(pattern, content):
            _add(match)

    if ids:
        return ids

    # 3. 裸数字回退（最低优先级）
    for num in re.findall(r"\b\d{8,}\b", content):
        _add(num)
    return ids


def _parse_ordinal(token: str) -> int:
    text = str(token or "").strip()
    if text.isdigit():
        return int(text)
    if text in ORDINAL_MAP:
        return ORDINAL_MAP[text]
    if text.startswith("十") and len(text) == 2 and text[1] in ORDINAL_MAP:
        return 10 + ORDINAL_MAP[text[1]]
    if text.endswith("十") and len(text) == 2 and text[0] in ORDINAL_MAP:
        return ORDINAL_MAP[text[0]] * 10
    if "十" in text:
        left, right = text.split("十", 1)
        tens = ORDINAL_MAP.get(left, 1) if left else 1
        ones = ORDINAL_MAP.get(right, 0) if right else 0
        return tens * 10 + ones
    return 0


def resolve_ordinal_references(text: str, search_results: list[dict]) -> list[str]:
    """从文本中解析指代（"第N张"、"这些图片"），返回对应的 picture_ids。"""
    if not search_results:
        return []

    content = str(text or "")
    ids = []
    seen = set()

    for ordinal in re.findall(r"第\s*([一二三四五六七八九十\d]+)\s*张", content):
        index = _parse_ordinal(ordinal)
        if index <= 0 or index > len(search_results):
            continue
        picture_id = str(search_results[index - 1].get("id") or "")
        if picture_id and picture_id not in seen:
            seen.add(picture_id)
            ids.append(picture_id)

    if ids:
        return ids

    if re.search(r"(这几张|这些图片|这些图|上述图片|上述图|上面这些|刚才这些|刚才的图片|搜索结果|全部图片|所有图片)", content):
        for item in search_results:
            picture_id = str(item.get("id") or "")
            if picture_id and picture_id not in seen:
                seen.add(picture_id)
                ids.append(picture_id)
    return ids
