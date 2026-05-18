from src.service.expert_common import build_expert_graph
from src.service.prompt import ANALYST_SYSTEM_PROMPT

ANALYST_TOOL_NAMES = {"analyze_space", "get_picture_detail"}


def build_analyst_agent():
    return build_expert_graph(
        prefix="analyst",
        system_prompt=ANALYST_SYSTEM_PROMPT,
        tool_names=ANALYST_TOOL_NAMES,
        inject_user_id_tools={"analyze_space", "get_picture_detail"},
        persist_tools={"analyze_space"},
        summary_instruction="请总结分析结果，用中文呈现。",
    )
