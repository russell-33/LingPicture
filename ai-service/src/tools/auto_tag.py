import logging
import httpx
from src.config import settings
from src.core.internal_auth import internal_headers
from src.service.llm import get_llm_client
from src.service.prompt import AUTO_TAG_PROMPT
from src.core.structured import parse_json_response, PictureAutoTagResult
from src.core.tag_schema import normalize_allowed_tags

logger = logging.getLogger(__name__)


def _auto_tag_single(picture_id: int, image_url: str, picture_name: str = "", space_id: int = 0,
                     user_id: int = 0) -> dict:
    """单张图片自动标注：视觉模型看图片 → 结构化输出元数据 → 写入数据库。"""
    client = get_llm_client()

    # Step 1: 视觉模型生成元数据
    # 构建消息：系统提示词 + 用户消息（含图片URL）
    role_map = {"system": "system", "human": "user", "ai": "assistant"}
    llm_messages = []
    for m in AUTO_TAG_PROMPT.format_messages():
        if m.type == "human":
            continue
        role = role_map.get(m.type, "user")
        llm_messages.append({"role": role, "content": m.content})

    user_content = [{"type": "text", "text": "请分析这张图片并生成元数据，只返回严格 JSON。"}]
    if image_url:
        user_content.insert(0, {"type": "image_url", "image_url": {"url": image_url}})
    llm_messages.append({"role": "user", "content": user_content})

    response = client.chat.completions.create(
        model="qwen-vl-plus",
        messages=llm_messages,
        temperature=0.2,
    )
    text = response.choices[0].message.content

    # Step 2: 解析结构化输出
    result = parse_json_response(text, PictureAutoTagResult)
    result.tags = normalize_allowed_tags(result.tags)

    # Step 3: 写入数据库（使用内部接口跳过鉴权）
    edit_body = {
        "id": picture_id,
        #"spaceId": space_id,
        "name": result.name,
        "tags": result.tags,
        "category": result.category,
        "introduction": result.introduction,
    }
    try:
        resp = httpx.post(
            f"{settings.java_backend_url}/picture/edit/internal",
            json=edit_body,
            headers=internal_headers(user_id),
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to write metadata to Java backend: {e}")


    return result.model_dump()
