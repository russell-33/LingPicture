import json


SEARCH_TOOLS = {"search_pictures_by_semantic", "search_pictures_by_tag"}


def summarize_tool_result(tool_name: str, result: str) -> dict:
    if tool_name not in SEARCH_TOOLS:
        return {}

    try:
        items = json.loads(result)
    except Exception:
        return {"last_search_results": [], "raw": str(result)[:1000]}

    summarized = []
    for idx, item in enumerate(items, start=1):
        summarized.append({
            "rank": idx,
            "id": item.get("id"),
            "name": item.get("name", ""),
            "url": item.get("url", ""),
            "score": item.get("score", 0),
        })
    return {"last_search_results": summarized}
