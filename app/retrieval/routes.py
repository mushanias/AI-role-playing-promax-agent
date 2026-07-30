"""公共固定知识库的只读状态接口。"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_knowledge_index_manifest
from app.retrieval.manifest import IndexManifest
from app.retrieval.schemas import KnowledgeBaseInfoResponse


router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/info", response_model=KnowledgeBaseInfoResponse)
async def get_knowledge_base_info(
    manifest: IndexManifest | None = Depends(
        get_knowledge_index_manifest
    ),
) -> KnowledgeBaseInfoResponse:
    """返回索引可用性，不加载向量模型。"""
    if manifest is None:
        return KnowledgeBaseInfoResponse(available=False)
    return KnowledgeBaseInfoResponse(
        available=True,
        knowledge_base_version=manifest.knowledge_base_version,
        embedding_model=manifest.embedding_model,
        document_count=manifest.document_count,
        chunk_count=manifest.chunk_count,
        built_at=manifest.built_at,
    )
