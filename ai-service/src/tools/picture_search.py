import json
import logging
import re
import httpx
from langchain_core.tools import tool
from src.config import settings
from src.core.internal_auth import internal_headers
from src.core.tag_utils import normalize_tag
from src.service.rag import rag_semantic_search

logger = logging.getLogger(__name__)


@tool
def search_pictures_by_semantic(query: str, space_id: int, top_k: int = 10, user_id: int = 0) -> str:
    """搜索图片：结合语义搜索和数据库关键词搜索，最后按图片 ID 去重。"""
    try:
        data = rag_semantic_search(query, space_id, top_k, generate_answer=False)
        pics = data.get("pictures", [])
        semantic_results = [
            _build_picture_result(p)
            for p in pics if p.get("rerank_score", p.get("score", 0)) > 0.3
        ]
        semantic_results = _filter_existing_semantic_results(semantic_results, space_id, user_id)
        db_results = _search_pictures_by_db(query, space_id, user_id, top_k)
        result = _merge_picture_results(semantic_results, db_results, top_k)
        if not result:
            return "未找到匹配的图片。"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"search_pictures_by_semantic error: {e}")
        return f"语义搜索失败：{str(e)}"


@tool
def search_pictures_by_tag(tag: str, space_id: int, user_id: int = 0, limit: int = 100) -> str:
    """按业务标签精确搜索图片：适合给某个或多个标签批量删除/编辑时先找出所有图片 ID。
    多个标签可用逗号分隔，命中任意一个标签即返回。"""
    if not user_id:
        return "缺少用户上下文，无法按标签查询图片。"

    targets = {normalize_tag(t) for t in re.split(r"[,，、]+", str(tag or "")) if t.strip()}
    if not targets:
        return "未提供有效的标签。"

    try:
        result = []
        seen = set()
        current = 1
        page_size = 20
        max_items = max(1, min(int(limit or 100), 200))

        while len(result) < max_items:
            resp = httpx.post(
                f"{settings.java_backend_url}/picture/list/page/vo/internal",
                json={"spaceId": space_id, "current": current, "pageSize": page_size},
                headers=internal_headers(user_id),
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {}) or {}
            records = data.get("records", []) or []
            if not records:
                break

            for record in records:
                if len(result) >= max_items:
                    break
                tags = _coerce_tags(record.get("tags", []))
                if not any(normalize_tag(t) in targets for t in tags):
                    continue
                picture_id = record.get("id")
                if not picture_id or picture_id in seen:
                    continue
                seen.add(picture_id)
                result.append({
                    "id": picture_id,
                    "name": record.get("name", ""),
                    "url": record.get("thumbnailUrl") or record.get("url", ""),
                    "tags": tags,
                    "score": 1.0,
                })

            pages = int(data.get("pages") or 0)
            total = int(data.get("total") or 0)
            if pages and current >= pages:
                break
            if not pages and total and current * page_size >= total:
                break
            current += 1

        if not result:
            return f"未找到带有“{tag}”标签的图片。"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"search_pictures_by_tag error: {e}")
        return f"按标签搜索失败：{str(e)}"


def _build_picture_result(pic: dict) -> dict:
    display_url = (
        pic.get("thumbnailUrl")
        or pic.get("thumbnail_url")
        or pic.get("url", "")
    )
    return {
        "id": pic["picture_id"],
        "name": pic.get("picture_name", ""),
        "url": display_url,
        "description": pic.get("description", ""),
        "score": round(pic.get("rerank_score", pic.get("score", 0)), 2),
    }


def _filter_existing_semantic_results(results: list[dict], space_id: int, user_id: int = 0) -> list[dict]:
    if not results or not user_id:
        return results

    filtered = []
    try:
        for item in results:
            picture_id = item.get("id")
            if not picture_id:
                continue
            resp = httpx.get(
                f"{settings.java_backend_url}/picture/get/vo/internal",
                params={"id": picture_id, "spaceId": space_id},
                headers=internal_headers(user_id),
                timeout=5.0,
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code", 0) != 0:
                logger.info("Drop stale semantic picture result %s: %s", picture_id, payload.get("message", "not found"))
                continue
            data = payload.get("data") or {}
            if not data.get("id"):
                continue
            filtered.append(_build_verified_picture_result(item, data))
        return filtered
    except Exception as e:
        logger.warning("semantic result existence validation failed, keeping original results: %s", e)
        return results


def _build_verified_picture_result(item: dict, data: dict) -> dict:
    verified = dict(item)
    verified["id"] = data.get("id", item.get("id"))
    verified["name"] = data.get("name") or item.get("name", "")
    verified["url"] = data.get("thumbnailUrl") or data.get("url") or item.get("url", "")
    verified["description"] = data.get("introduction") or item.get("description", "")
    tags = _coerce_tags(data.get("tags", []))
    if tags:
        verified["tags"] = tags
    return verified


def _search_pictures_by_db(query: str, space_id: int, user_id: int = 0, limit: int = 10) -> list[dict]:
    if not user_id or not str(query).strip():
        return []

    try:
        max_items = max(1, min(int(limit or 10), 100))
        result = []
        seen = set()
        for search_text in _build_db_search_queries(query):
            if len(result) >= max_items:
                break
            resp = httpx.post(
                f"{settings.java_backend_url}/picture/list/page/vo/internal",
                json={
                    "spaceId": space_id,
                    "current": 1,
                    "pageSize": min(max_items, 20),
                    "searchText": search_text,
                },
                headers=internal_headers(user_id),
                timeout=10.0,
            )
            resp.raise_for_status()
            records = (resp.json().get("data", {}) or {}).get("records", []) or []
            for record in records:
                picture_id = record.get("id")
                if not picture_id or picture_id in seen:
                    continue
                seen.add(picture_id)
                result.append(_build_db_picture_result(record))
                if len(result) >= max_items:
                    break
        return result
    except Exception as e:
        logger.warning(f"database picture search failed for query '{query}': {e}")
        return []


def _build_db_search_queries(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []

    queries = [text]
    parts = [p for p in re.split(r"[\s,，、]+", text) if p]
    queries.extend(parts)

    english_parts = [p for p in parts if re.search(r"[A-Za-z]", p)]
    if len(english_parts) > 1:
        queries.append(" ".join(english_parts))

    deduped = []
    seen = set()
    for q in queries:
        key = q.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    return deduped[:8]


def _build_db_picture_result(record: dict) -> dict:
    return {
        "id": record["id"],
        "name": record.get("name", ""),
        "url": record.get("thumbnailUrl") or record.get("url", ""),
        "description": record.get("introduction", ""),
        "score": 0.85,
    }


def _merge_picture_results(semantic_results: list[dict], db_results: list[dict], top_k: int) -> list[dict]:
    merged = []
    by_id = {}

    for item in semantic_results + db_results:
        picture_id = item.get("id")
        if not picture_id:
            continue
        if picture_id not in by_id:
            copy = dict(item)
            copy["_order"] = len(merged)
            by_id[picture_id] = copy
            merged.append(copy)
            continue

        existing = by_id[picture_id]
        if not existing.get("name") and item.get("name"):
            existing["name"] = item["name"]
        if not existing.get("url") and item.get("url"):
            existing["url"] = item["url"]
        if not existing.get("description") and item.get("description"):
            existing["description"] = item["description"]
        existing["score"] = max(existing.get("score", 0), item.get("score", 0))

    limit = max(1, int(top_k or 10))
    ranked = sorted(merged, key=lambda x: (-float(x.get("score", 0)), x.get("_order", 0)))
    for item in ranked:
        item.pop("_order", None)
    return ranked[:limit]


def _coerce_tags(value) -> list[str]:
    if isinstance(value, list):
        return [str(t) for t in value if str(t).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(t) for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            return [value] if value.strip() else []
    return []
