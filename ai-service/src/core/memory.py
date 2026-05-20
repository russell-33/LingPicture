import json
import time
from typing import Optional

from src.config import settings

# Redis 在 Phase 2.5 为可选依赖，未安装时默认使用内存存储
try:
    import redis
    _redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db, decode_responses=True)
    _redis_client.ping()
    USE_REDIS = True
except Exception:
    _redis_client = None
    USE_REDIS = False
    _memory_store: dict[str, dict] = {}

SESSION_TTL = 3600 * 24  # 24 hours


def _make_key(session_id: str, kind: str) -> str:
    return f"yunpicture:{kind}:{session_id}"


def _save_json(key: str, value: dict, ttl: int) -> None:
    """Serialize a dict to JSON and persist to Redis or in-memory store."""
    data = json.dumps(value, ensure_ascii=False)
    if USE_REDIS:
        _redis_client.setex(key, ttl, data)
    else:
        _memory_store[key] = {"data": data, "expires": time.time() + ttl}


def _load_json(key: str) -> Optional[dict]:
    """Load and deserialize a JSON value; returns None when key is absent or expired."""
    if USE_REDIS:
        raw = _redis_client.get(key)
        return json.loads(raw) if raw else None
    entry = _memory_store.get(key)
    if entry is None or entry["expires"] < time.time():
        return None
    return json.loads(entry["data"])


def _delete_key(key: str) -> None:
    """Remove a key from Redis or in-memory store."""
    if USE_REDIS:
        _redis_client.delete(key)
    else:
        _memory_store.pop(key, None)


def save_messages(session_id: str, messages: list[dict]) -> None:
    _save_json(_make_key(session_id, "messages"), {"messages": messages}, SESSION_TTL)


def load_messages(session_id: str) -> list[dict]:
    data = _load_json(_make_key(session_id, "messages"))
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return list(data.get("messages", []))


def clear_messages(session_id: str) -> None:
    _delete_key(_make_key(session_id, "messages"))


def save_summary(session_id: str, summary: str) -> None:
    """Persist a conversation summary with longer TTL."""
    _save_json(_make_key(session_id, "summary"), {"summary": summary}, SESSION_TTL * 7)


def load_summary(session_id: str) -> str:
    """Load a previously persisted conversation summary."""
    data = _load_json(_make_key(session_id, "summary"))
    return str(data.get("summary", "")) if data else ""


