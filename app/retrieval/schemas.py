"""公共知识库 HTTP 接口的数据模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseInfoResponse(BaseModel):
    """前端连接设置页可展示的知识库状态。"""

    model_config = ConfigDict(extra="forbid")

    available: bool
    knowledge_base_version: str | None = None
    embedding_model: str | None = None
    document_count: int = 0
    chunk_count: int = 0
    built_at: datetime | None = None

