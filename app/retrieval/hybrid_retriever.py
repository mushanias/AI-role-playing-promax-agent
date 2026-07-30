"""并行执行关键词和向量检索，并融合两路排名。"""

import asyncio
import json
from pathlib import Path

from app.retrieval.contracts import (
    KnowledgeHit,
    KnowledgeIndex,
    KnowledgeRetrievalResult,
    TextEmbedder,
)
from app.retrieval.keyword_index import SQLiteKeywordIndex
from app.retrieval.manifest import IndexManifest
from app.retrieval.vector_index import FaissVectorIndex


class HybridKnowledgeRetriever:
    """使用倒数排名融合，隔离不同索引的分数尺度。"""

    def __init__(
        self,
        knowledge_base_version: str,
        keyword_index: KnowledgeIndex,
        vector_index: KnowledgeIndex,
        rank_constant: int = 60,
    ) -> None:
        if rank_constant <= 0:
            raise ValueError("rank_constant 必须大于 0")
        self.knowledge_base_version = knowledge_base_version
        self.keyword_index = keyword_index
        self.vector_index = vector_index
        self.rank_constant = rank_constant

    @classmethod
    def from_directory(
        cls,
        index_directory: str | Path,
        embedder: TextEmbedder,
    ) -> "HybridKnowledgeRetriever":
        """根据部署目录组装只读混合检索器。"""
        directory = Path(index_directory)
        manifest = IndexManifest.model_validate_json(
            (directory / "index_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        return cls(
            knowledge_base_version=manifest.knowledge_base_version,
            keyword_index=SQLiteKeywordIndex(
                directory / "keyword.sqlite"
            ),
            vector_index=FaissVectorIndex(
                index_path=directory / "vectors.faiss",
                metadata_path=directory / "metadata.json",
                manifest=manifest,
                embedder=embedder,
            ),
        )

    async def retrieve(
        self,
        query: str,
        limit: int = 6,
    ) -> KnowledgeRetrievalResult:
        """两路检索可以独立降级，只有全部失败时返回空结果。"""
        candidate_limit = max(limit * 2, limit)
        keyword_task = asyncio.to_thread(
            self.keyword_index.search,
            query,
            candidate_limit,
        )
        vector_task = asyncio.to_thread(
            self.vector_index.search,
            query,
            candidate_limit,
        )
        results = await asyncio.gather(
            keyword_task,
            vector_task,
            return_exceptions=True,
        )

        warnings: list[str] = []
        rankings: list[list[KnowledgeHit]] = []
        names = ("关键词索引", "向量索引")
        for name, result in zip(names, results):
            if isinstance(result, BaseException):
                warnings.append(f"{name}不可用，已执行降级")
            else:
                rankings.append(result)

        hits = _reciprocal_rank_fusion(
            rankings,
            limit,
            self.rank_constant,
        )
        return KnowledgeRetrievalResult(
            knowledge_base_version=self.knowledge_base_version,
            hits=tuple(hits),
            warnings=tuple(warnings),
        )


class UnavailableKnowledgeRetriever:
    """索引尚未构建时使用的显式空实现。"""

    def __init__(self, reason: str = "公共知识库尚未构建") -> None:
        self.reason = reason

    async def retrieve(
        self,
        query: str,
        limit: int = 6,
    ) -> KnowledgeRetrievalResult:
        return KnowledgeRetrievalResult(
            knowledge_base_version="unavailable",
            warnings=(self.reason,),
        )


def load_index_manifest(
    index_directory: str | Path,
) -> IndexManifest | None:
    """在不初始化模型的情况下读取知识库状态。"""
    path = Path(index_directory) / "index_manifest.json"
    if not path.exists():
        return None
    return IndexManifest.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def _reciprocal_rank_fusion(
    rankings: list[list[KnowledgeHit]],
    limit: int,
    rank_constant: int,
) -> list[KnowledgeHit]:
    scores: dict[str, float] = {}
    records: dict[str, KnowledgeHit] = {}

    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + (
                1.0 / (rank_constant + rank)
            )
            records.setdefault(hit.chunk_id, hit)

    ordered_ids = sorted(
        scores,
        key=lambda chunk_id: (-scores[chunk_id], chunk_id),
    )
    return [
        records[chunk_id].model_copy(
            update={"score": scores[chunk_id]}
        )
        for chunk_id in ordered_ids[:limit]
    ]
