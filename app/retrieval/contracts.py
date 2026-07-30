"""公共知识库上游可以依赖的稳定契约。"""

from datetime import datetime
from typing import Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeHit(BaseModel):
    """关键词或向量索引返回的一条知识片段。"""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    score: float


class KnowledgeRetrievalResult(BaseModel):
    """一次公共知识库检索的完整结果。"""

    model_config = ConfigDict(extra="forbid")

    knowledge_base_version: str
    hits: tuple[KnowledgeHit, ...] = ()
    warnings: tuple[str, ...] = ()


class TextEmbedder(Protocol):
    """固定本地向量模型的最小能力。"""

    @property
    def model_name(self) -> str:
        """返回索引绑定的模型名称。"""

    @property
    def dimension(self) -> int:
        """返回向量维度。"""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """批量生成归一化文本向量。"""


class KnowledgeIndex(Protocol):
    """单路只读知识索引。"""

    def search(self, query: str, limit: int) -> list[KnowledgeHit]:
        """按相关度从高到低返回知识片段。"""


class KnowledgeRetriever(Protocol):
    """应用层依赖的公共知识库入口。"""

    async def retrieve(
        self,
        query: str,
        limit: int = 6,
    ) -> KnowledgeRetrievalResult:
        """执行一次混合检索。"""

