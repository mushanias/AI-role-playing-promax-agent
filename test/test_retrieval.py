"""公共知识库构建、单路检索和混合融合测试。"""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.dependencies import get_knowledge_index_manifest
from app.main import app
from app.retrieval.builder import KnowledgeBaseBuilder
from app.retrieval.contracts import KnowledgeHit
from app.retrieval.hybrid_retriever import (
    HybridKnowledgeRetriever,
    UnavailableKnowledgeRetriever,
)
from app.retrieval.manifest import SourceDocument, SourceManifest
from app.retrieval.manifest import IndexManifest


NOW = datetime(2026, 7, 30, tzinfo=UTC)


class FakeEmbedder:
    """用三个维度提供完全可预测的离线测试向量。"""

    model_name = "test-embedding"
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            if "数学" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "英语" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


class FailingIndex:
    def search(self, query: str, limit: int):
        raise OSError("索引暂不可用")


class StaticIndex:
    def __init__(self, hits: list[KnowledgeHit]) -> None:
        self.hits = hits

    def search(self, query: str, limit: int):
        return self.hits[:limit]


class KnowledgeBaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.sources = self.root / "sources"
        self.indexes = self.root / "indexes"
        self.sources.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_source_manifest(self) -> None:
        (self.sources / "math.md").write_text(
            "高等数学研究函数、极限和积分。\n\n"
            "极限是微积分中的基础概念。",
            encoding="utf-8",
        )
        (self.sources / "english.md").write_text(
            "考研英语需要词汇、阅读和写作训练。",
            encoding="utf-8",
        )
        manifest = SourceManifest(
            knowledge_base_version="test-1",
            embedding_model="test-embedding",
            documents=(
                SourceDocument(
                    document_id="math",
                    title="高等数学资料",
                    source_path="math.md",
                    url="https://example.com/math",
                    publisher="测试出版社",
                    published_at=NOW,
                ),
                SourceDocument(
                    document_id="english",
                    title="英语资料",
                    source_path="english.md",
                ),
            ),
        )
        (self.sources / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    async def test_build_and_hybrid_retrieve(self) -> None:
        self.write_source_manifest()
        embedder = FakeEmbedder()
        manifest = KnowledgeBaseBuilder(embedder).build(
            self.sources,
            self.indexes,
        )
        retriever = HybridKnowledgeRetriever.from_directory(
            self.indexes,
            embedder,
        )

        result = await retriever.retrieve("高等数学极限", limit=2)

        self.assertEqual(manifest.chunk_count, 2)
        self.assertEqual(result.knowledge_base_version, "test-1")
        self.assertEqual(result.hits[0].document_id, "math")
        self.assertEqual(result.warnings, ())
        self.assertGreaterEqual(len(embedder.calls), 2)

    async def test_one_index_failure_keeps_other_results(self) -> None:
        hit = KnowledgeHit(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="资料",
            content="有效内容",
            score=0.8,
        )
        retriever = HybridKnowledgeRetriever(
            knowledge_base_version="test-1",
            keyword_index=StaticIndex([hit]),
            vector_index=FailingIndex(),
        )

        result = await retriever.retrieve("问题")

        self.assertEqual(result.hits[0].chunk_id, "chunk-1")
        self.assertEqual(result.warnings, ("向量索引不可用，已执行降级",))

    async def test_unavailable_retriever_is_explicit(self) -> None:
        result = await UnavailableKnowledgeRetriever().retrieve("问题")

        self.assertEqual(result.hits, ())
        self.assertIn("尚未构建", result.warnings[0])

    def test_empty_manifest_build_does_not_load_embedding_model(self) -> None:
        embedder = FakeEmbedder()
        manifest = SourceManifest(
            knowledge_base_version="empty-1",
            embedding_model="test-embedding",
        )
        (self.sources / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

        built = KnowledgeBaseBuilder(embedder).build(
            self.sources,
            self.indexes,
        )

        self.assertEqual(built.chunk_count, 0)
        self.assertEqual(embedder.calls, [])


class KnowledgeBaseRouteTests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_info_returns_deployed_manifest(self) -> None:
        manifest = IndexManifest(
            knowledge_base_version="exam-1",
            embedding_model="test-embedding",
            embedding_dimension=3,
            document_count=2,
            chunk_count=4,
            built_at=NOW,
        )
        app.dependency_overrides[get_knowledge_index_manifest] = (
            lambda: manifest
        )

        response = TestClient(app).get("/knowledge-base/info")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])
        self.assertEqual(
            response.json()["knowledge_base_version"],
            "exam-1",
        )


if __name__ == "__main__":
    unittest.main()
