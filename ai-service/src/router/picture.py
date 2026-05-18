import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.structured import PictureAutoTagResult
from src.tools.auto_tag import _auto_tag_single

router = APIRouter(prefix="/picture", tags=["picture"])
logger = logging.getLogger(__name__)


class AutoTagResponse(BaseModel):
    picture_id: int
    name: str
    category: str
    tags: list[str]
    introduction: str


class AutoTagRequest(BaseModel):
    image_url: str = ""
    picture_name: str = ""
    space_id: int = 0
    user_id: int = 0


@router.post("/auto-tag/{picture_id}")
def auto_tag(picture_id: int, req: AutoTagRequest = AutoTagRequest()):
    """按键触发的自动标注 API。视觉模型看图片 → 生成元数据 → 写入数据库。"""
    try:
        result = _auto_tag_single(picture_id, req.image_url, req.picture_name, req.space_id, req.user_id)
        return result
    except Exception as e:
        logger.error(f"auto-tag failed for picture {picture_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
