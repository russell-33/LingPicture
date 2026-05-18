"""
RAG 管道: Query改写 → 多路混合检索 → 去重融合 → LLM Rerank → 答案生成
"""

import json
import logging
from src.service.llm import chat, get_embedding_single
from src.service.prompt import RAG_SEMANTIC_SEARCH_PROMPT
from src.vector_store.chroma_store import hybrid_search, get_collection

logger = logging.getLogger(__name__)


# ─── Query 改写 ───────────────────────────────────────────

REWRITE_PROMPT = """将用户的图片搜索意图扩展为1-3个不同的搜索短语，覆盖同义词和相关概念。
用逗号分隔，不要编号，不要解释。

示例:
用户: "蓝色背景海报"
输出: 蓝色背景极简海报, 蓝色系品牌宣传图, 冷色调企业海报

用户: "{query}"
输出:"""


def rewrite_query(query: str) -> list[str]:
    """用 LLM 将用户 query 扩展为多个变体，覆盖同义词和相关概念。"""
    prompt = REWRITE_PROMPT.format(query=query)
    try:
        result = chat([{"role": "user", "content": prompt}], max_tokens=100, temperature=0.3)
        # 解析逗号分隔的结果
        variants = [q.strip() for q in result.replace("\n", ",").split(",") if q.strip()]
        # 去重，保留原 query
        seen = {query}
        unique = [query]
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        logger.info(f"Query rewritten: {query} → {unique}")
        return unique[:3]
    except Exception as e:
        logger.warning(f"Query rewrite failed: {e}")
        return [query]


# ─── LLM Rerank ───────────────────────────────────────────

def _call_rerank_api(query: str, documents: list[str]) -> list[float]:
    """调用 DashScope 专用 Rerank API，批量计算相关性分数。"""
    import httpx
    from src.config import settings

    resp = httpx.post(
        settings.rerank_base_url,
        headers={
            "Authorization": f"Bearer {settings.rerank_api_key or settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.rerank_model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": len(documents),
                "return_documents": False,
            },
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("output", {}).get("results", [])
    scores = [0.0] * len(documents)
    for item in results:
        idx = item.get("index", 0)
        scores[idx] = item.get("relevance_score", 0.0)
    return scores


def llm_rerank(query: str, candidates: list[dict]) -> list[dict]:
    """用 qwen3-rerank 专用模型批量重排序，一次 API 调用处理所有候选。"""
    if len(candidates) <= 1:
        return candidates

    # 构建文档列表（描述文本）
    documents = []
    for pic in candidates:
        desc = pic.get("description", "") or f"{pic.get('picture_name', '')}"
        documents.append(desc[:500])

    try:
        scores = _call_rerank_api(query, documents)
        for i, pic in enumerate(candidates):
            pic["rerank_score"] = round(scores[i], 4) if i < len(scores) else 0.0
    except Exception as e:
        logger.warning(f"Rerank API failed, falling back to raw scores: {e}")
        for pic in candidates:
            pic["rerank_score"] = pic.get("score", 0.0)

    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    logger.info(f"qwen3-rerank: {len(candidates)} candidates scored for '{query[:30]}'")
    return candidates


# ─── 多路召回融合 ─────────────────────────────────────────

def multi_route_recall(query: str, space_id: int, top_k: int = 10,
                       use_rewrite: bool = True, use_hybrid: bool = True) -> list[dict]:
    """多路召回 + 去重融合。
    - use_rewrite: 是否启用 Query 改写扩展
    - use_hybrid: 是否启用 BM25+向量混合检索（否则纯向量）
    """
    queries = rewrite_query(query) if use_rewrite else [query]
    all_results: dict[int, dict] = {}  # picture_id → result

    for q in queries:
        if use_hybrid:
            results = hybrid_search(space_id, q, top_k)
        else:
            from src.vector_store.chroma_store import search_pictures
            results = search_pictures(space_id, q, top_k)

        for pic in results:
            pid = pic["picture_id"]
            if pid not in all_results or pic.get("score", 0) > all_results[pid].get("score", 0):
                all_results[pid] = pic

    merged = sorted(all_results.values(), key=lambda x: x.get("score", 0), reverse=True)
    logger.info(f"Multi-route: {len(queries)} queries, {len(merged)} unique results for space {space_id}")
    return merged[:top_k * 2]  # 多返回一些给 rerank


# ─── 完整 RAG 管道 ────────────────────────────────────────

def rag_semantic_search(query: str, space_id: int, top_k: int = 10,
                        enable_rewrite: bool = True,
                        enable_hybrid: bool = True,
                        enable_rerank: bool = True,
                        generate_answer: bool = True) -> dict:
    """完整的 RAG 语义搜索管道：
    1. Query 改写扩展
    2. 多路混合检索（BM25 + 向量）
    3. 去重融合
    4. LLM 重排序
    5. LLM 组织回答
    """
    # Step 1-3: 多路召回
    candidates = multi_route_recall(query, space_id, top_k,
                                    use_rewrite=enable_rewrite,
                                    use_hybrid=enable_hybrid)

    if not candidates:
        return {"pictures": [], "answer": "没有找到匹配的图片。"}

    # Step 4: LLM Rerank
    if enable_rerank and len(candidates) > 1:
        candidates = llm_rerank(query, candidates)

    # 取 top_k
    top = candidates[:top_k]

    if not generate_answer:
        return {"pictures": top, "answer": ""}

    # Step 5: LLM 组织回答
    context_parts = []
    for pic in top:
        score = pic.get("rerank_score", pic.get("score", 0))
        context_parts.append(
            f"图片ID: {pic['picture_id']}, 名称: {pic.get('picture_name', '')}, "
            f"描述: {pic.get('description', '')}, 相关度: {score:.1f}"
        )
    context = "\n".join(context_parts)

    msgs = RAG_SEMANTIC_SEARCH_PROMPT.format_messages(query=query, context=context)
    llm_msgs = [{"role": msg.type, "content": msg.content} for msg in msgs]
    answer = chat(llm_msgs)

    return {"pictures": top, "answer": answer}
