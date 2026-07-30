"""公共固定知识库的离线构建程序。"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.retrieval.chunking import KnowledgeChunk, TextChunker
from app.retrieval.contracts import TextEmbedder
from app.retrieval.manifest import IndexManifest, SourceManifest


class KnowledgeBaseBuilder:
    """把人工维护的权威文本构建为两个只读索引。"""

    def __init__(
        self,
        embedder: TextEmbedder,
        chunker: TextChunker | None = None,
    ) -> None:
        self.embedder = embedder
        self.chunker = chunker or TextChunker()

    def build(
        self,
        source_directory: str | Path,
        output_directory: str | Path,
    ) -> IndexManifest:
        """执行可重复构建并返回产物清单。"""
        source_root = Path(source_directory)
        output_root = Path(output_directory)
        source_manifest = SourceManifest.model_validate_json(
            (source_root / "manifest.json").read_text(encoding="utf-8")
        )
        if source_manifest.embedding_model != self.embedder.model_name:
            raise ValueError("源清单的向量模型与构建器不一致")

        chunks = self._load_chunks(source_root, source_manifest)
        output_root.mkdir(parents=True, exist_ok=True)
        self._build_keyword_index(
            output_root / "keyword.sqlite",
            chunks,
        )
        self._build_vector_index(
            output_root / "vectors.faiss",
            output_root / "metadata.json",
            chunks,
        )

        manifest = IndexManifest(
            knowledge_base_version=(
                source_manifest.knowledge_base_version
            ),
            embedding_model=self.embedder.model_name,
            embedding_dimension=self.embedder.dimension,
            document_count=len(source_manifest.documents),
            chunk_count=len(chunks),
            built_at=datetime.now(UTC),
        )
        (output_root / "index_manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return manifest

    def _load_chunks(
        self,
        source_root: Path,
        manifest: SourceManifest,
    ) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for document in manifest.documents:
            source_path = document.resolve_source(source_root)
            if not source_path.exists():
                raise FileNotFoundError(
                    f"知识库资料不存在：{document.source_path}"
                )
            content = source_path.read_text(encoding="utf-8")
            chunks.extend(self.chunker.split(document, content))
        return chunks

    @staticmethod
    def _build_keyword_index(
        database_path: Path,
        chunks: list[KnowledgeChunk],
    ) -> None:
        temporary_path = database_path.with_suffix(".sqlite.tmp")
        if temporary_path.exists():
            temporary_path.unlink()

        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute(
                """
                CREATE VIRTUAL TABLE chunks USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    title,
                    content,
                    url UNINDEXED,
                    publisher UNINDEXED,
                    published_at UNINDEXED,
                    tokenize='trigram'
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO chunks(
                    chunk_id,
                    document_id,
                    title,
                    content,
                    url,
                    publisher,
                    published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.title,
                        chunk.content,
                        chunk.url,
                        chunk.publisher,
                        chunk.published_at,
                    )
                    for chunk in chunks
                ],
            )
            connection.commit()
        finally:
            connection.close()

        temporary_path.replace(database_path)

    def _build_vector_index(
        self,
        index_path: Path,
        metadata_path: Path,
        chunks: list[KnowledgeChunk],
    ) -> None:
        import faiss

        index = faiss.IndexFlatIP(self.embedder.dimension)
        if chunks:
            vectors = np.asarray(
                self.embedder.embed(
                    [chunk.content for chunk in chunks]
                ),
                dtype="float32",
            )
            if vectors.shape != (
                len(chunks),
                self.embedder.dimension,
            ):
                raise ValueError("构建向量数量或维度与知识片段不一致")
            index.add(vectors)

        temporary_index = index_path.with_suffix(".faiss.tmp")
        faiss.write_index(index, str(temporary_index))
        temporary_index.replace(index_path)

        metadata = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "title": chunk.title,
                "content": chunk.content,
                "url": chunk.url,
                "publisher": chunk.publisher,
                "published_at": chunk.published_at,
            }
            for chunk in chunks
        ]
        temporary_metadata = metadata_path.with_suffix(".json.tmp")
        temporary_metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_metadata.replace(metadata_path)
