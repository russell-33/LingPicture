from langchain_core.tools import tool

from src.tools.picture_search import search_pictures_by_semantic, search_pictures_by_tag
from src.tools.space_analyze import analyze_space
from src.tools.picture_edit import get_picture_detail, edit_picture

TOOLS = [
    search_pictures_by_semantic,
    search_pictures_by_tag,
    get_picture_detail,
    analyze_space,
    edit_picture,
]


def get_tools_list() -> list[dict]:
    """返回 OpenAI 兼容格式的工具列表，供 LLM Function Calling 使用。"""
    result = []
    for t in TOOLS:
        schema = t.args_schema.schema() if t.args_schema else {}
        result.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": schema,
            }
        })
    return result


def execute_tool(name: str, args: dict) -> str:
    for t in TOOLS:
        if t.name == name:
            return t.invoke(args)
    return f"Tool not found: {name}"
