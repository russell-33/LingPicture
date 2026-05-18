from src.service.expert_common import build_expert_graph
from src.service.prompt import ANALYST_SYSTEM_PROMPT

ANALYST_TOOL_NAMES = {"analyze_space"}


def build_analyst_agent():
    return build_expert_graph(
        prefix="analyst",
        system_prompt=ANALYST_SYSTEM_PROMPT,
        tool_names=ANALYST_TOOL_NAMES,
        inject_user_id_tools={"analyze_space"},
        persist_tools={"analyze_space"},
        summary_instruction=(
            "请保留分析结果的分区结构和小图标，用中文整齐呈现；不要改写成一整段长文本。"
            "不要使用 Markdown 表格，不要输出图片样例速览。"
            "项目分类固定为：模板、电商、表情包、素材、海报、其他；不要建议新建或自定义分类。"
        ),
    )
