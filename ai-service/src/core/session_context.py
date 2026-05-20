from src.core.context import slide_window
from src.core.memory import load_messages, load_summary, save_summary
from src.service.context_persistence import load_durable_session_summary
from src.service.prompt import AGENT_SYSTEM_PROMPT


def build_agent_messages(session_id: str, task: str, space_id: str, user_id: int, max_tokens: int = 8000) -> list[dict]:
    prompt = (
        AGENT_SYSTEM_PROMPT
        + f"\n\n当前可信用户 ID: {user_id}。"
        + f"\n当前用户正在空间 ID {space_id} 中操作。"
        + f"\n搜索图片和分析空间时 space_id 必须为 {space_id}，严禁使用其他值。"
    )

    context_messages = []
    summary = load_summary(session_id)
    if not summary:
        summary = load_durable_session_summary(session_id, user_id)
        if summary:
            save_summary(session_id, summary)
    if summary:
        context_messages.append({"role": "system", "content": f"历史摘要：{summary}"})

    history = [m for m in load_messages(session_id) if m.get("role") != "system"]
    history.extend(context_messages)
    history.append({"role": "user", "content": task})

    return slide_window(history, prompt, max_tokens=max_tokens)
