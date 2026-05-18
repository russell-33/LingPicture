from src.core.context import count_message_tokens


def should_compact(messages: list[dict], threshold_tokens: int = 6000) -> bool:
    return count_message_tokens(messages) > threshold_tokens


def build_compact_prompt(messages: list[dict]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "请把下面对话压缩为结构化中文摘要，保留用户目标、空间、图片选择、未完成任务和偏好，不要编造。",
        },
        {"role": "user", "content": str(messages)},
    ]
