import tempfile
import unittest
import pickle
from pathlib import Path
from unittest.mock import patch

from src.vector_store import chroma_store


class FakeCollection:
    def __init__(self):
        self.get_all_calls = 0
        self.add_calls = []

    def get(self, ids=None):
        if ids is not None:
            return {"ids": []}

        self.get_all_calls += 1
        return {
            "ids": ["1"],
            "documents": ["红色汽车在海边"],
            "metadatas": [{"picture_name": "红色汽车", "url": "https://example.com/car.jpg"}],
        }

    def add(self, ids, embeddings, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "embeddings": embeddings,
            "documents": documents,
            "metadatas": metadatas,
        })


class FakeEmptyCollection:
    def get(self, ids=None):
        return {"ids": [], "documents": [], "metadatas": []}

    def count(self):
        return 0


class Bm25PersistenceTest(unittest.TestCase):
    def setUp(self):
        if hasattr(chroma_store, "_bm25_index_cache"):
            chroma_store._bm25_index_cache.clear()

    def test_hybrid_search_reuses_persisted_bm25_index_without_rebuilding_collection(self):
        collection = FakeCollection()

        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.object(chroma_store.settings, "chroma_data_dir", str(Path(tmpdir) / "chroma")), \
                patch("src.vector_store.chroma_store.get_collection", return_value=collection), \
                patch("src.vector_store.chroma_store.search_pictures", return_value=[]):
            first = chroma_store.hybrid_search(7, "汽车海边", top_k=5, alpha=0)
            chroma_store._bm25_index_cache.clear()
            second = chroma_store.hybrid_search(7, "汽车海边", top_k=5, alpha=0)

            self.assertEqual([1], [item["picture_id"] for item in first])
            self.assertEqual([1], [item["picture_id"] for item in second])
            self.assertEqual(1, collection.get_all_calls)
            self.assertTrue((Path(tmpdir) / "bm25" / "space_7.pkl").exists())

    def test_add_picture_index_invalidates_persisted_bm25_index(self):
        collection = FakeCollection()

        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.object(chroma_store.settings, "chroma_data_dir", str(Path(tmpdir) / "chroma")), \
                patch("src.vector_store.chroma_store.get_collection", return_value=collection), \
                patch("src.vector_store.chroma_store.search_pictures", return_value=[]), \
                patch("src.service.llm.get_embedding_single", return_value=[0.1, 0.2]):
            chroma_store.hybrid_search(7, "汽车海边", top_k=5, alpha=0)
            cache_path = Path(tmpdir) / "bm25" / "space_7.pkl"
            self.assertTrue(cache_path.exists())

            chroma_store.add_picture_index(7, 2, "新的蓝色汽车", {"picture_name": "蓝色汽车"})

            self.assertFalse(cache_path.exists())
            self.assertEqual(1, len(collection.add_calls))

    def test_hybrid_search_invalidates_persisted_bm25_when_collection_is_empty(self):
        stale_index = {
            "doc_count": 1,
            "avgdl": 1,
            "docs": {
                "99": {
                    "tokens": ["赛车"],
                    "len": 1,
                    "meta": {"picture_name": "已删除赛车", "url": "https://example.com/deleted.jpg"},
                }
            },
            "df": {"赛车": 1},
            "id_to_pid": {"99": 99},
        }

        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.object(chroma_store.settings, "chroma_data_dir", str(Path(tmpdir) / "chroma")), \
                patch("src.vector_store.chroma_store.get_collection", return_value=FakeEmptyCollection()), \
                patch("src.vector_store.chroma_store.search_pictures", return_value=[]):
            cache_path = Path(tmpdir) / "bm25" / "space_7.pkl"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("wb") as f:
                pickle.dump({"version": chroma_store._BM25_CACHE_VERSION, "index": stale_index}, f)

            result = chroma_store.hybrid_search(7, "赛车", top_k=5, alpha=0)

            self.assertEqual([], result)
            self.assertFalse(cache_path.exists())


if __name__ == "__main__":
    unittest.main()
