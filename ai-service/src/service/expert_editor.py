from src.service.expert_common import build_expert_graph
from src.service.prompt import EDITOR_SYSTEM_PROMPT

EDITOR_TOOL_NAMES = {"edit_picture", "get_picture_detail"}


def build_editor_agent():
    return build_expert_graph(
        prefix="editor",
        system_prompt=EDITOR_SYSTEM_PROMPT,
        tool_names=EDITOR_TOOL_NAMES,
        inject_user_id_tools={"get_picture_detail", "edit_picture"},
        persist_tools={"edit_picture", "get_picture_detail"},
        summary_instruction="请总结编辑结果，用中文告知用户成功多少、失败多少。",
    )
