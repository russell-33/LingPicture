import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from langchain_core.tools import tool
from src.config import settings
from src.core.internal_auth import internal_headers
from src.core.tag_utils import normalize_tag

logger = logging.getLogger(__name__)


@tool
def get_picture_detail(picture_id: int, space_id: int, user_id: int = 0) -> str:
    """获取图片详情：根据图片ID获取完整信息（名称、标签、分类、尺寸、URL等）。"""
    try:
        resp = httpx.get(
            f"{settings.java_backend_url}/picture/get/vo/internal",
            params={"id": picture_id, "spaceId": space_id},
            headers=internal_headers(user_id),
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return json.dumps({
            "id": data.get("id"),
            "name": data.get("name", ""),
            "tags": data.get("tags", []),
            "category": data.get("category", ""),
            "introduction": data.get("introduction", ""),
            "picSize": data.get("picSize"),
            "picWidth": data.get("picWidth"),
            "picHeight": data.get("picHeight"),
            "url": data.get("url", ""),
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"get_picture_detail error: {e}")
        return f"获取图片详情失败：{str(e)}"


@tool
def edit_picture(picture_ids: str, space_id: int, tags: str = "", remove_tags: str = "",
                 category: str = "", name: str = "", introduction: str = "", user_id: int = 0) -> str:
    """批量编辑图片：传入逗号分隔的图片 ID 列表，批量修改标签、分类、名称或简介。
    picture_ids 如 '101,102,103'。
    tags 为要添加的新标签（逗号分隔），会自动和已有标签合并去重，不会覆盖旧标签。
    remove_tags 为要删除的标签（逗号分隔），会从已有标签中移除。"""
    try:
        ids = [int(x.strip()) for x in picture_ids.split(",") if x.strip()]
        if not ids:
            return "未提供有效的图片 ID。"

        new_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        remove_tag_set = {normalize_tag(t) for t in remove_tags.split(",") if t.strip()} if remove_tags else None

        def edit_one(pid):
            # 先获取已有标签
            existing_tags = []
            try:
                resp = httpx.get(
                    f"{settings.java_backend_url}/picture/get/vo/internal",
                    params={"id": pid, "spaceId": space_id},
                    headers=internal_headers(user_id),
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    existing_tags = data.get("tags") or []
            except Exception:
                pass

            # 处理标签：先删除，再添加
            final_tags = list(existing_tags)
            if remove_tag_set:
                final_tags = [t for t in final_tags if normalize_tag(t) not in remove_tag_set]
            if new_tags:
                existing_norms = {normalize_tag(t) for t in final_tags}
                for tag in new_tags:
                    tag_norm = normalize_tag(tag)
                    if tag_norm and tag_norm not in existing_norms:
                        final_tags.append(tag)
                        existing_norms.add(tag_norm)

            body = {"id": pid, "spaceId": space_id}
            if name:
                body["name"] = name
            if final_tags != list(existing_tags):
                body["tags"] = final_tags
            if category:
                body["category"] = category
            if introduction:
                body["introduction"] = introduction
            try:
                logger.info(f"edit_picture POST body for {pid}: {json.dumps(body, ensure_ascii=False)}")
                resp = httpx.post(
                    f"{settings.java_backend_url}/picture/edit/internal",
                    json=body,
                    headers=internal_headers(user_id),
                    timeout=10.0,
                )
                logger.info(f"edit_picture response for {pid}: status={resp.status_code}, body={resp.text[:200]}")
                if resp.status_code != 200:
                    return (pid, False)
                resp_body = resp.json()
                if resp_body.get("code") != 0:
                    logger.error(f"edit_picture business error for {pid}: {resp_body}")
                    return (pid, False)
                return (pid, True)
            except Exception:
                return (pid, False)

        success = 0
        errors = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(edit_one, pid): pid for pid in ids}
            for f in as_completed(futures):
                pid, ok = f.result()
                if ok:
                    success += 1
                else:
                    errors.append(f"ID {pid}")

        msg = f"成功编辑 {success}/{len(ids)} 张图片。"
        if errors:
            msg += f" 失败: {', '.join(errors[:5])}"
        return msg
    except Exception as e:
        logger.error(f"edit_picture error: {e}")
        return f"编辑图片失败：{str(e)}"
