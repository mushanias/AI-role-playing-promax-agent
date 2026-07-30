"""把权威资料稳定切分为可检索片段。"""

import hashlib
from dataclasses import dataclass

from app.retrieval.manifest import SourceDocument


@dataclass(frozen=True)
class KnowledgeChunk:
    """离线构建阶段使用的完整知识片段。"""

    chunk_id: str
    document_id: str
    title: str
    content: str
    url: str | None
    publisher: str | None
    published_at: str | None


class TextChunker:
    """优先按段落切分，并为过长段落提供稳定窗口。"""

    def __init__(
        self,
        max_characters: int = 1000,
        overlap_characters: int = 150,
    ) -> None:
        if max_characters < 200:
            raise ValueError("max_characters 不能小于 200")
        if not 0 <= overlap_characters < max_characters:
            raise ValueError("overlap_characters 必须小于最大长度")
        self.max_characters = max_characters
        self.overlap_characters = overlap_characters

    def split(
        self,
        document: SourceDocument,
        content: str,
    ) -> list[KnowledgeChunk]:
        """返回内容非空、ID 稳定的知识片段。"""
        normalized = content.replace("\r\n", "\n").strip()
        if not normalized:
            return []

        paragraphs = [
            paragraph.strip()
            for paragraph in normalized.split("\n\n")
            if paragraph.strip()
        ]
        texts: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            candidate = f"{buffer}\n\n{paragraph}".strip()
            if buffer and len(candidate) > self.max_characters:
                texts.extend(self._split_long_text(buffer))
                buffer = paragraph
            else:
                buffer = candidate
        if buffer:
            texts.extend(self._split_long_text(buffer))

        chunks: list[KnowledgeChunk] = []
        for index, text in enumerate(texts):
            digest = hashlib.sha256(
                f"{document.document_id}:{index}:{text}".encode("utf-8")
            ).hexdigest()[:20]
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document.document_id}-{digest}",
                    document_id=document.document_id,
                    title=document.title,
                    content=text,
                    url=document.url,
                    publisher=document.publisher,
                    published_at=(
                        document.published_at.isoformat()
                        if document.published_at
                        else None
                    ),
                )
            )
        return chunks

    def _split_long_text(self, text: str) -> list[str]:
        if len(text) <= self.max_characters:
            return [text]

        step = self.max_characters - self.overlap_characters
        return [
            text[start : start + self.max_characters].strip()
            for start in range(0, len(text), step)
            if text[start : start + self.max_characters].strip()
        ]

