import logging
import httpx

from src.config import settings
from src.core.internal_auth import internal_headers

logger = logging.getLogger(__name__)


def load_durable_session_summary(session_id: str, user_id: int) -> str:
    try:
        resp = httpx.get(
            f"{settings.java_backend_url}/ai/internal/context/session-summary",
            params={"sessionId": session_id},
            headers=internal_headers(user_id),
            timeout=3.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        return str(data.get("summary") or "")
    except Exception as exc:
        logger.debug("加载持久化会话摘要跳过：%s", exc)
        return ""


def persist_session_summary(session_id: str, user_id: int, space_id: str, title: str, summary: str) -> None:
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "space_id": space_id,
        "title": title,
        "summary": summary,
    }
    try:
        httpx.post(
            f"{settings.java_backend_url}/ai/internal/context/session-summary",
            json=payload,
            headers=internal_headers(user_id),
            timeout=3.0,
        ).raise_for_status()
    except Exception as exc:
        logger.warning("持久化会话摘要失败：%s", exc)


def persist_operation_log(session_id: str, user_id: int, space_id: str, operation_type: str,
                          tool_name: str, target_ids: str, request_text: str,
                          result_summary: str, status: str = "SUCCESS") -> None:
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "space_id": space_id,
        "operation_type": operation_type,
        "tool_name": tool_name,
        "target_ids": target_ids,
        "request_text": request_text,
        "result_summary": result_summary,
        "status": status,
    }
    try:
        httpx.post(
            f"{settings.java_backend_url}/ai/internal/context/operation-log",
            json=payload,
            headers=internal_headers(user_id),
            timeout=3.0,
        ).raise_for_status()
    except Exception as exc:
        logger.warning("持久化操作日志失败：%s", exc)
