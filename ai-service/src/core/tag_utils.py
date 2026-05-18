import re


def normalize_tag(tag: str) -> str:
    return re.sub(r"\s+", " ", str(tag or "").strip()).casefold()


def clean_tag(tag: str) -> str:
    return str(tag or "").strip().strip("`\"'“”‘’「」『』，。；;:：")


def extract_remove_tags(text: str) -> list[str]:
    content = str(text or "")
    tags = []

    def add_tag(raw: str) -> None:
        tag = clean_tag(raw)
        if not tag:
            return
        if normalize_tag(tag) in {normalize_tag(item) for item in tags}:
            return
        tags.append(tag)

    explicit = re.search(r'remove_tags\s*=\s*["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
    if explicit:
        for part in re.split(r"[,，、]+", explicit.group(1)):
            add_tag(part)
        if tags:
            return tags

    for quoted in re.findall(r"[\"'“‘「『]([^\"'”’」』]+)[\"'”’」』]\s*标签", content, flags=re.IGNORECASE):
        add_tag(quoted)
    if tags:
        return tags

    patterns = [
        r"删除.*?的\s*([^，。；\n]+?)\s*标签",
        r"删除\s*([^，。；\n]+?)\s*标签",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if not match:
            continue
        for part in re.split(r"\s*(?:和|及|与|、|,|，)\s*", match.group(1)):
            add_tag(part)
        if tags:
            return tags
    return tags


def extract_remove_tag(text: str) -> str:
    return ",".join(extract_remove_tags(text))


def extract_add_tag(text: str) -> str:
    content = str(text or "")
    patterns = [
        r"(?:加上|添加|新增|打上)\s*([^，。；\n]+?)\s*标签",
        r"加\s*([^，。；\n]+?)\s*标签",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            tag = clean_tag(match.group(1))
            if tag:
                return tag
    return ""
