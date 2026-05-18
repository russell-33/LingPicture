from src.service.expert_common import build_expert_graph
from src.service.prompt import SEARCHER_SYSTEM_PROMPT

SEARCHER_TOOL_NAMES = {"search_pictures_by_semantic", "search_pictures_by_tag", "get_picture_detail"}


def build_searcher_agent():
    return build_expert_graph(
        prefix="searcher",
        system_prompt=SEARCHER_SYSTEM_PROMPT,
        tool_names=SEARCHER_TOOL_NAMES,
        inject_user_id_tools={"search_pictures_by_semantic", "search_pictures_by_tag", "get_picture_detail"},
        summary_instruction="请根据搜索结果给用户一个清晰的总结。列出找到的图片（含 id 和名称），如果没有找到就说未找到。",
    )
