import json
import re
from typing import TypeVar, Type, Optional
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class PictureAutoTagResult(BaseModel):
    name: str
    category: str
    tags: list[str]
    introduction: str


class SemanticSearchResult(BaseModel):
    pictures: list[dict]
    answer: str


def parse_json_response(text: str, schema: Type[T]) -> T:
    """从 LLM 响应的文本中提取 JSON 并校验为指定 Pydantic 模型。"""
    # 尝试匹配 ```json ... ``` 包裹的内容
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1)

    # 尝试匹配第一个完整的 JSON 对象/数组
    json_match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
    if json_match:
        text = json_match.group(0)

    data = _loads_json_lenient(text)
    return schema.model_validate(data)


def _loads_json_lenient(text: str):
    """兼容部分视觉模型返回的 JSON-like 文本，例如未给字段名加双引号。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = text.strip()
        repaired = re.sub(r"//.*?$", "", repaired, flags=re.MULTILINE)
        repaired = re.sub(r"/\*[\s\S]*?\*/", "", repaired)
        repaired = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', repaired)
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        return json.loads(repaired)


def parse_json_response_safe(text: str, schema: Type[T]) -> Optional[T]:
    try:
        return parse_json_response(text, schema)
    except (json.JSONDecodeError, ValidationError):
        return None
