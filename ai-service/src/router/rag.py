import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.service.picture_desc import generate_picture_description
from src.service.rag import rag_semantic_search
from src.vector_store.chroma_store import add_picture_index, remove_picture_index, get_index_status, search_pictures

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger(__name__)


class PictureSearchRequest(BaseModel):
    query: str
    space_id: int
    top_k: int = 10


class BuildIndexRequest(BaseModel):
    space_id: int
    picture_ids: list[int]
    image_urls: list[str] = []      # 对应每张图片的 URL（可选）
    descriptions: list[str] = []    # 预生成的描述文本（可选，优先使用）
    picture_names: list[str] = []   # 图片名称（可选）


class EvaluateRequest(BaseModel):
    test_queries: list[str]
    space_id: int


@router.post("/picture/search")
def picture_search(req: PictureSearchRequest):
    return rag_semantic_search(req.query, req.space_id, req.top_k)


@router.post("/picture/build-index")
def build_picture_index(req: BuildIndexRequest):
    indexed = 0
    errors = []
    for i, pid in enumerate(req.picture_ids):
        try:
            name = req.picture_names[i] if i < len(req.picture_names) else f"Picture {pid}"
            # 优先用传入的 description，其次用图片 URL 调视觉模型
            if i < len(req.descriptions) and req.descriptions[i]:
                description = req.descriptions[i]
            else:
                url = req.image_urls[i] if i < len(req.image_urls) else ""
                description = generate_picture_description(url) if url else f"图片 {pid}：{name}"

            add_picture_index(req.space_id, pid, description,
                              {"picture_name": name,
                               "url": req.image_urls[i] if i < len(req.image_urls) else ""})
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to index picture {pid}: {e}")
            errors.append({"picture_id": pid, "error": str(e)})
    return {"indexed": indexed, "errors": errors}


@router.delete("/picture/index/{picture_id}")
def delete_picture_index(picture_id: int, space_id: int):
    remove_picture_index(space_id, picture_id)
    return {"ok": True}


@router.get("/picture/index/status/{space_id}")
def picture_index_status(space_id: int):
    return get_index_status(space_id)


@router.post("/evaluate")
def evaluate_rag(req: EvaluateRequest):
    total_precision = 0.0
    total_recall = 0.0
    n = len(req.test_queries)

    for query in req.test_queries:
        results = search_pictures(req.space_id, query, top_k=10)
        # 简单评估：计算相关图片的命中率 (以 score > 0.5 为相关)
        relevant = sum(1 for p in results if p["score"] > 0.5)
        total_precision += relevant / max(len(results), 1)
        total_recall += relevant / 10.0  # 假设相关图片至少有 1 张

    return {
        "avg_precision": round(total_precision / max(n, 1), 3),
        "avg_recall": round(total_recall / max(n, 1), 3),
    }
