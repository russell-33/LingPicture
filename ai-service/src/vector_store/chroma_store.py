import logging
import math
import pickle
from collections import defaultdict
from pathlib import Path
from typing import Optional

import jieba

import chromadb
from chromadb.config import Settings as ChromaSettings
from src.config import settings

logger = logging.getLogger(__name__)

_client: Optional[chromadb.PersistentClient] = None
_BM25_CACHE_VERSION = 1
_bm25_index_cache: dict[int, dict] = {}


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_data_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(space_id: int) -> chromadb.Collection:
    client = get_client()
    name = f"space_{space_id}_pictures"
    return client.get_or_create_collection(name=name)


def add_picture_index(space_id: int, picture_id: int, description: str,
                      metadata: Optional[dict] = None) -> None:
    """将图片描述向量化并存入 ChromaDB。"""
    from src.service.llm import get_embedding_single

    collection = get_collection(space_id)
    embedding = get_embedding_single(description)
    meta = metadata or {}
    meta["picture_id"] = picture_id

    # 如果已存在则更新
    existing = collection.get(ids=[str(picture_id)])
    if existing and existing["ids"]:
        collection.update(ids=[str(picture_id)], embeddings=[embedding], documents=[description], metadatas=[meta])
    else:
        collection.add(ids=[str(picture_id)], embeddings=[embedding], documents=[description], metadatas=[meta])

    _invalidate_bm25_index(space_id)
    logger.info(f"Indexed picture {picture_id} in space {space_id}")


def remove_picture_index(space_id: int, picture_id: int) -> None:
    collection = get_collection(space_id)
    collection.delete(ids=[str(picture_id)])
    _invalidate_bm25_index(space_id)


def search_pictures(space_id: int, query: str, top_k: int = 10) -> list[dict]:
    """向量语义搜索。"""
    from src.service.llm import get_embedding_single
    collection = get_collection(space_id)
    query_embedding = get_embedding_single(query)
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    pictures = []
    if results and results["ids"] and results["ids"][0]:
        for i, pid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            doc = results["documents"][0][i] if results["documents"] else ""
            dist = results["distances"][0][i] if results["distances"] else 0
            pictures.append({
                "picture_id": int(pid),
                "picture_name": meta.get("picture_name", ""),
                "url": meta.get("url", ""),
                "description": doc,
                "score": 1.0 - min(dist, 1.0),
            })
    return pictures


# ─── BM25 关键词检索 ──────────────────────────────────────

def _get_bm25_cache_dir() -> Path:
    return Path(settings.chroma_data_dir).parent / "bm25"


def _get_bm25_cache_path(space_id: int) -> Path:
    return _get_bm25_cache_dir() / f"space_{space_id}.pkl"


def _empty_bm25_index() -> dict:
    return {"doc_count": 0, "avgdl": 0, "docs": {}, "df": {}, "id_to_pid": {}}


def _collection_is_empty(collection: chromadb.Collection) -> bool:
    try:
        return collection.count() == 0
    except Exception:
        return False


def _load_bm25_index(space_id: int) -> Optional[dict]:
    cache_path = _get_bm25_cache_path(space_id)
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("rb") as f:
            payload = pickle.load(f)
        if not isinstance(payload, dict) or payload.get("version") != _BM25_CACHE_VERSION:
            return None
        index = payload.get("index")
        if not isinstance(index, dict):
            return None
        _bm25_index_cache[space_id] = index
        return index
    except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError, TypeError) as exc:
        logger.warning("Failed to load BM25 cache for space %s: %s", space_id, exc)
        try:
            cache_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _save_bm25_index(space_id: int, index: dict) -> None:
    cache_path = _get_bm25_cache_path(space_id)
    tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("wb") as f:
            pickle.dump({"version": _BM25_CACHE_VERSION, "index": index}, f)
        tmp_path.replace(cache_path)
    except OSError as exc:
        logger.warning("Failed to save BM25 cache for space %s: %s", space_id, exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _invalidate_bm25_index(space_id: int) -> None:
    _bm25_index_cache.pop(space_id, None)
    cache_path = _get_bm25_cache_path(space_id)
    try:
        cache_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to invalidate BM25 cache for space %s: %s", space_id, exc)


def _get_bm25_index(space_id: int, collection: chromadb.Collection) -> dict:
    if _collection_is_empty(collection):
        _invalidate_bm25_index(space_id)
        return _empty_bm25_index()

    cached = _bm25_index_cache.get(space_id)
    if cached is not None:
        return cached

    persisted = _load_bm25_index(space_id)
    if persisted is not None:
        return persisted

    index = _build_bm25_index(collection)
    _bm25_index_cache[space_id] = index
    _save_bm25_index(space_id, index)
    return index

def _tokenize(text: str) -> list[str]:  # 下划线前缀表示模块私有函数（类似 Java 的 private 方法，但 Python 仅是约定）
    """使用 jieba 进行中文分词。"""
    text = str(text).lower()  # 转小写
    tokens = jieba.lcut(text)  # jieba 精确模式分词
    return [t.strip() for t in tokens if t.strip()]  # 过滤空白 token


def _build_bm25_index(collection: chromadb.Collection) -> dict:
    """从 ChromaDB collection 构建内存 BM25 索引。"""
    data = collection.get()
    if not data or not data["ids"]:
        return _empty_bm25_index()

    docs = {}
    df = defaultdict(int)
    total_len = 0
    id_to_pid = {}

    for i, doc_id in enumerate(data["ids"]):
        text = data["documents"][i] if data["documents"] else ""
        meta = data["metadatas"][i] if data["metadatas"] else {}
        tokens = _tokenize(text)
        docs[doc_id] = {"tokens": tokens, "len": len(tokens), "meta": meta}
        id_to_pid[doc_id] = int(doc_id)
        for t in set(tokens):
            df[t] += 1
        total_len += len(tokens)

    avgdl = total_len / max(len(docs), 1)
    return {"doc_count": len(docs), "avgdl": avgdl, "docs": docs, "df": dict(df), "id_to_pid": id_to_pid}


def _bm25_search(index: dict, query: str, top_k: int = 10) -> list[dict]:
    """在 BM25 索引中搜索，返回带分数的结果列表。"""
    if not index["doc_count"]:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    k1, b = 1.5, 0.75
    N = index["doc_count"]
    avgdl = index["avgdl"]

    scores = {}
    for qt in query_tokens:
        qtf = query_tokens.count(qt)
        df_t = index["df"].get(qt, 0)
        if df_t == 0:
            continue
        idf = math.log((N - df_t + 0.5) / (df_t + 0.5) + 1.0)

        for doc_id, doc in index["docs"].items():
            tf = doc["tokens"].count(qt)
            if tf == 0:
                continue
            numerator = tf * (k1 + 1) * qtf
            denominator = tf + k1 * (1 - b + b * doc["len"] / max(avgdl, 1))
            score = idf * numerator / denominator
            scores[doc_id] = scores.get(doc_id, 0) + score

    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    max_score = max([s for _, s in sorted_docs]) if sorted_docs else 1.0

    results = []
    for doc_id, bm25_score in sorted_docs:
        doc = index["docs"].get(doc_id, {})
        meta = doc.get("meta", {})
        results.append({
            "picture_id": index["id_to_pid"].get(doc_id, int(doc_id)),
            "picture_name": meta.get("picture_name", ""),
            "url": meta.get("url", ""),
            "description": "",
            "score": bm25_score / max_score if max_score > 0 else 0,
        })
    return results


def hybrid_search(space_id: int, query: str, top_k: int = 10, alpha: float = 0.7) -> list[dict]:
    """混合检索：向量语义（权重 alpha）+ BM25 关键词（权重 1-alpha）。
    alpha=0.7 表示向量占 70%，BM25 占 30%。
    """
    collection = get_collection(space_id)

    # 向量检索
    vector_results = search_pictures(space_id, query, top_k)

    # BM25 检索
    bm25_index = _get_bm25_index(space_id, collection)
    bm25_results = _bm25_search(bm25_index, query, top_k)

    # 加权融合
    merged: dict[int, dict] = {}
    for pic in vector_results:
        pid = pic["picture_id"]
        merged[pid] = {**pic, "hybrid_score": pic.get("score", 0) * alpha}

    for pic in bm25_results:
        pid = pic["picture_id"]
        bm25_score = pic.get("score", 0) * (1 - alpha)
        if pid in merged:
            merged[pid]["hybrid_score"] = merged[pid].get("hybrid_score", 0) + bm25_score
            # 补充 vector 结果中可能缺失的字段
            if not merged[pid].get("url") and pic.get("url"):
                merged[pid]["url"] = pic["url"]
        else:
            merged[pid] = {**pic, "hybrid_score": bm25_score}

    sorted_results = sorted(merged.values(), key=lambda x: x["hybrid_score"], reverse=True)
    for r in sorted_results:
        r["score"] = round(r.pop("hybrid_score", r.get("score", 0)), 4)

    logger.info(f"Hybrid search: {len(vector_results)} vector + {len(bm25_results)} BM25 → {len(sorted_results)} merged")
    return sorted_results[:top_k]


def get_index_status(space_id: int) -> dict:
    collection = get_collection(space_id)
    return {
        "space_id": space_id,
        "indexed_count": collection.count(),
    }
