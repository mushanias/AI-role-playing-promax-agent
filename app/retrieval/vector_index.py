"""FAISS 向量索引的只读适配器。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.retrieval.contracts import KnowledgeHit, TextEmbedder
from app.retrieval.manifest import IndexManifest


class FaissVectorIndex:
    """延迟加载 FAISS 文件和片段元数据。"""

    def __init__(
        self,
        index_path: str | Path,
        metadata_path: str | Path,
        manifest: IndexManifest,
        embedder: TextEmbedder,
    ) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.manifest = manifest
        self.embedder = embedder
        self._index: Any | None = None
        self._metadata: list[dict] | None = None
        self._validate_configuration()

    def search(self, query: str, limit: int) -> list[KnowledgeHit]:
        """使用内积搜索已经归一化的语义向量。"""
        cleaned = query.strip()
        if not cleaned or limit <= 0 or self.manifest.chunk_count == 0:
            return []

        index, metadata = self._load()
        vector = np.asarray(
            self.embedder.embed([cleaned]),
            dtype="float32",
        )
        scores, positions = index.search(
            vector,
            min(limit, self.manifest.chunk_count),
        )

        hits: list[KnowledgeHit] = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0:
                continue
            item = metadata[int(position)]
            hits.append(
                KnowledgeHit(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    title=item["title"],
                    content=item["content"],
                    url=item.get("url"),
                    publisher=item.get("publisher"),
                    published_at=_parse_datetime(
                        item.get("published_at")
                    ),
                    score=float(score),
                )
            )
        return hits

    def _validate_configuration(self) -> None:
        if self.manifest.embedding_model != self.embedder.model_name:
            raise ValueError("运行时向量模型与知识库索引不一致")
        if self.manifest.embedding_dimension != self.embedder.dimension:
            raise ValueError("运行时向量维度与知识库索引不一致")

    def _load(self):
        if self._index is not None and self._metadata is not None:
            return self._index, self._metadata
        if not self.index_path.exists() or not self.metadata_path.exists():
            raise FileNotFoundError("向量索引或元数据不存在")

        import faiss

        self._index = faiss.read_index(str(self.index_path))
        self._metadata = json.loads(
            self.metadata_path.read_text(encoding="utf-8")
        )
        if self._index.ntotal != len(self._metadata):
            raise ValueError("FAISS 向量数量与元数据数量不一致")
        return self._index, self._metadata


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

