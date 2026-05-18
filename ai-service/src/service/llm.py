import time
import logging
from typing import Optional
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
from src.config import settings

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None

MAX_RETRIES = 3
RETRY_DELAY = 2.0


class LLMError(Exception):
    pass


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


_ROLE_MAP = {"human": "user", "ai": "assistant", "system": "system", "user": "user", "assistant": "assistant", "tool": "tool"}


def _normalize_messages(messages: list) -> list[dict]:
    result = []
    for m in messages:
        if hasattr(m, 'type'):
            role = _ROLE_MAP.get(m.type, m.type)
            content = getattr(m, 'content', '')
            entry = {"role": role, "content": content}
            if hasattr(m, 'tool_call_id') and m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            result.append(entry)
        elif isinstance(m, dict):
            role = _ROLE_MAP.get(m.get("role", ""), m.get("role", "user"))
            entry = {"role": role, "content": m.get("content", "")}
            if m.get("tool_call_id"):
                entry["tool_call_id"] = m["tool_call_id"]
            if m.get("tool_calls"):
                entry["tool_calls"] = m["tool_calls"]
            result.append(entry)
        else:
            result.append({"role": "user", "content": str(m)})
    return result


def _retry(func, *args, **kwargs):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"LLM call attempt {attempt + 1} failed, retrying in {RETRY_DELAY}s: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
        except APIError as e:
            raise LLMError(f"API error: {e}") from e
    raise LLMError(f"LLM call failed after {MAX_RETRIES} retries: {last_error}")


def chat(messages: list[dict], model: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    client = get_llm_client()
    return _retry(
        lambda: client.chat.completions.create(
            model=model or settings.llm_model,
            messages=_normalize_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
    ).choices[0].message.content


def chat_with_tools(messages: list[dict], tools: list[dict], model: str = None, temperature: float = 0.7):
    client = get_llm_client()
    return _retry(
        lambda: client.chat.completions.create(
            model=model or settings.llm_model,
            messages=messages,
            tools=tools,
            temperature=temperature,
        )
    ).choices[0].message


def get_embedding(texts: list[str]) -> list[list[float]]:
    client = OpenAI(api_key=settings.embedding_api_key, base_url=settings.embedding_base_url)
    resp = _retry(lambda: client.embeddings.create(model=settings.embedding_model, input=texts))
    return [item.embedding for item in resp.data]


def get_embedding_single(text: str) -> list[float]:
    return get_embedding([text])[0]
