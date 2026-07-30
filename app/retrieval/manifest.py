"""公共知识库源清单和构建产物清单。"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceDocument(BaseModel):
    """一份由开发者提前整理的权威文本资料。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    url: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None

    def resolve_source(self, source_directory: Path) -> Path:
        """解析并限制资料路径只能位于知识库源目录。"""
        source_root = source_directory.resolve()
        source_path = (source_root / self.source_path).resolve()
        if source_root not in source_path.parents:
            raise ValueError("知识库资料路径不能离开 sources 目录")
        if source_path.suffix.lower() not in {".md", ".txt"}:
            raise ValueError("MVP 公共知识库只接受 Markdown 和纯文本")
        return source_path


class SourceManifest(BaseModel):
    """离线构建程序读取的人工维护清单。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    knowledge_base_version: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    documents: tuple[SourceDocument, ...] = ()

    @model_validator(mode="after")
    def validate_document_ids(self) -> "SourceManifest":
        ids = [document.document_id for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("知识库 document_id 不能重复")
        return self


class IndexManifest(BaseModel):
    """随索引部署、供运行时校验的构建产物清单。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    knowledge_base_version: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    built_at: datetime

