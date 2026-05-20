import json


SEARCH_TOOLS = {"search_pictures_by_semantic", "search_pictures_by_tag"}
MAX_SEARCH_ROUNDS = 5


def summarize_tool_result(tool_name: str, result: str) -> list[dict]:
    """将搜索工具的原始结果转为精简列表。非搜索工具返回空列表。"""
    if tool_name not in SEARCH_TOOLS:
        return []

    try:
        items = json.loads(result)
    except Exception:
        return []

    summarized = []
    for idx, item in enumerate(items, start=1):
        summarized.append({
            "rank": idx,
            "id": item.get("id"),
            "name": item.get("name", ""),
            "url": item.get("url", ""),
            "score": item.get("score", 0),
        })
    return summarized


def append_search_round(tool_context: dict, results: list[dict], query: str = "") -> dict:
    """将新一轮搜索结果追加到 tool_context，保留最近 MAX_SEARCH_ROUNDS 轮。"""
    rounds = list(tool_context.get("search_rounds", []))
    rounds.append({"results": results, "query": query})
    if len(rounds) > MAX_SEARCH_ROUNDS:
        rounds = rounds[-MAX_SEARCH_ROUNDS:]
    tool_context["search_rounds"] = rounds
    tool_context["last_search_results"] = results
    return tool_context


def get_all_search_results(tool_context: dict) -> list[dict]:
    """获取所有轮次的搜索结果，按轮次倒序、去重。"""
    rounds = tool_context.get("search_rounds", [])
    if not rounds:
        return tool_context.get("last_search_results", [])

    all_results = []
    seen = set()
    for r in reversed(rounds):
        for item in r.get("results", []):
            item_id = item.get("id")
            if item_id and item_id not in seen:
                seen.add(item_id)
                all_results.append(item)
    return all_results
