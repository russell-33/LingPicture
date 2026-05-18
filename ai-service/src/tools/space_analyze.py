import json
import logging
import httpx
from langchain_core.tools import tool
from src.config import settings
from src.core.internal_auth import internal_headers
from src.service.llm import chat
from src.service.prompt import SPACE_ANALYZE_PROMPT

logger = logging.getLogger(__name__)


def _extract_response_data(resp: httpx.Response, label: str, default):
    resp.raise_for_status()
    payload = resp.json()
    code = payload.get("code")
    if code != 0:
        message = payload.get("msg") or payload.get("message") or code
        raise ValueError(f"{label}接口返回异常：{message}")
    data = payload.get("data")
    return default if data is None else data


def _to_int(value) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _sum_counts(items: list[dict]) -> int:
    return sum(_to_int(item.get("count")) for item in items if isinstance(item, dict))


def _build_space_counter_warning(results: dict) -> str:
    usage = results.get("usage") or {}
    categories = results.get("category") or []
    tags = results.get("tags") or []
    used_count = _to_int(usage.get("usedCount"))
    used_size = _to_int(usage.get("usedSize"))

    if used_count != 0:
        return ""
    if _sum_counts(categories) == 0 and _sum_counts(tags) == 0:
        return ""

    return (
        "空间统计数据不一致：space 表聚合字段通过分析接口返回 "
        f"usedCount={used_count}、usedSize={used_size}，"
        "但分类/标签统计接口已经统计到图片数据。当前空间用量分析必须以 space 表为准，"
        "因此不会用 picture 表统计结果覆盖 usedCount。请先同步或修复 space.totalCount / "
        "space.totalSize 后再重新分析。"
    )


@tool
def analyze_space(space_id: int, user_id: int = 0) -> str:
    """分析空间：获取空间的使用统计（图片数量、存储用量、分类分布、标签排行），并用中文总结。"""
    try:
        results = {}

        # 获取用量分析
        resp = httpx.post(
            f"{settings.java_backend_url}/space/analyze/usage/internal",
            json={"spaceId": space_id},
            headers=internal_headers(user_id),
            timeout=10.0,
        )
        results["usage"] = _extract_response_data(resp, "空间用量分析", {})

        # 获取分类分析
        resp = httpx.post(
            f"{settings.java_backend_url}/space/analyze/category/internal",
            json={"spaceId": space_id},
            headers=internal_headers(user_id),
            timeout=10.0,
        )
        results["category"] = _extract_response_data(resp, "空间分类分析", [])

        # 获取标签分析
        resp = httpx.post(
            f"{settings.java_backend_url}/space/analyze/tag/internal",
            json={"spaceId": space_id},
            headers=internal_headers(user_id),
            timeout=10.0,
        )
        results["tags"] = _extract_response_data(resp, "空间标签分析", [])

        if not results:
            return "获取空间数据失败，请检查空间ID是否正确。"
        logger.info("space analyze data for space %s: %s", space_id, json.dumps(results, ensure_ascii=False)[:1000])
        counter_warning = _build_space_counter_warning(results)
        if counter_warning:
            return counter_warning

        # 用 LLM 总结
        msgs = SPACE_ANALYZE_PROMPT.format_messages(
            data=json.dumps(results, ensure_ascii=False),
            query=(
                "请分析这个空间的数据。注意：usage 字段来自 space 表的 totalCount / totalSize，"
                "如果 usage.usedCount 大于 0，严禁判断为空间没有图片；"
                "如果分类或标签为空，只说明对应维度暂无统计，不代表空间没有图片。"
            )
        )
        llm_msgs = [{"role": msg.type, "content": msg.content} for msg in msgs]
        return chat(llm_msgs)
    except Exception as e:
        logger.error(f"analyze_space error: {e}")
        return f"空间分析失败：{str(e)}"
