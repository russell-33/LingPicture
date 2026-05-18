import logging
import math
from functools import lru_cache

from src.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_qwen_tokenizer():
    """Load the Qwen tokenizer lazily so service startup does not depend on HF cache."""
    try:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(
            settings.qwen_tokenizer_model,
            trust_remote_code=True,
            local_files_only=settings.qwen_tokenizer_local_only,
        )
    except Exception as exc:
        logger.warning("Qwen tokenizer unavailable, falling back to conservative token estimate: %s", exc)
        return None


def _estimate_qwen_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def _normalize_messages(messages: list[dict]) -> list[dict]:
    return [
        {
            "role": str(msg.get("role", "user")),
            "content": str(msg.get("content", "")),
        }
        for msg in messages
    ]


def _encode_count(tokenizer, text: str) -> int:
    try:
        return len(tokenizer.encode(text, add_special_tokens=False))
    except TypeError:
        return len(tokenizer.encode(text))


def count_tokens(text: str) -> int:
    text = str(text)
    tokenizer = _get_qwen_tokenizer()
    if tokenizer is None:
        return _estimate_qwen_tokens(text)
    return _encode_count(tokenizer, text)


def count_message_tokens(messages: list[dict]) -> int:
    normalized = _normalize_messages(messages)
    if not normalized:
        return 0

    tokenizer = _get_qwen_tokenizer()
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            rendered = tokenizer.apply_chat_template(
                normalized,
                tokenize=False,
                add_generation_prompt=False,
            )
            return _encode_count(tokenizer, rendered)
        except Exception as exc:
            logger.debug("Qwen chat template token count failed, falling back to per-message count: %s", exc)

    total = 0
    for msg in normalized:
        total += count_tokens(str(msg.get("content", "")))
        total += 4  # role + overhead
    return total


def slide_window(messages: list[dict], system_prompt: str, max_tokens: int = 8000) -> list[dict]:
    """保留系统提示词 + 最近的对话消息，不超过 max_tokens。"""
    system_tokens = count_message_tokens([{"role": "system", "content": system_prompt}])
    remaining = max_tokens - system_tokens

    result = []
    # 从后往前取消息
    used = 0
    for msg in reversed(messages):
        tok = count_message_tokens([msg])
        if used + tok > remaining:
            break
        result.insert(0, msg)
        used += tok

    # 始终在头部插入系统消息
    result.insert(0, {"role": "system", "content": system_prompt})
    return result
