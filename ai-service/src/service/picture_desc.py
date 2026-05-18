import logging
from src.service.llm import get_llm_client

logger = logging.getLogger(__name__)

DESC_PROMPT = "请用一段中文描述这张图片的内容、颜色、构图、风格。150 字以内。"


def generate_picture_description(image_url: str) -> str:
    """用视觉模型看图片，生成一段自然语言描述。"""
    client = get_llm_client()
    response = client.chat.completions.create(
        model="qwen-vl-plus",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": DESC_PROMPT},
            ]
        }]
    )
    return response.choices[0].message.content
