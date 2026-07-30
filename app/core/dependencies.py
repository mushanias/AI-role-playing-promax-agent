"""依赖提供者：集中管理 FastAPI 的依赖注入。"""

from functools import lru_cache

from app.core.config import (
    CONTEXT_HIGH_WATERMARK,
    CONTEXT_LOW_WATERMARK,
    CONTEXT_SAFETY_MARGIN,
    CONVERSATIONS_PATH,
    KNOWLEDGE_BASE_INDEX_PATH,
    MAX_COMPRESSION_PASSES,
    PERFORMANCE_METRICS_PATH,
    RECENT_RAW_TOKEN_TARGET,
    SUMMARY_TOKEN_BUDGET,
)
from app.conversations.branch_service import BranchService
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.conversation_service import ConversationService
from app.conversations.memory.context_builder import ContextBuilder
from app.conversations.memory.context_planner import ContextPlanner
from app.conversations.memory.llm_compressor import LLMCompressor
from app.conversations.memory.token_counter import TokenCounter
from app.conversations.memory.versioned_context_compression_service import (
    CompressionBatchPlanner,
    VersionedContextCompressionService,
)
from app.conversations.memory.versioned_context_manager import (
    VersionedContextManager,
)
from app.conversations.versioned_chat_service import VersionedChatService
from app.llm import llm_model
from app.llm.client import LLMClient
from app.llm.runtime_factory import RuntimeLLMFactory
from app.learning.application.context_service import LearningContextService
from app.learning.application.path_validator import ActivePathValidator
from app.learning.application.snapshot_adapter import CompactGraphAdapter
from app.learning.application.turn_orchestrator import (
    LearningTurnOrchestrator,
)
from app.learning.domain.graph_policy import LearningGraphPolicy
from app.learning.observability import LoggingLearningObserver
from app.performance.recorder import CsvPerformanceRecorder
from app.retrieval.embedding import FastEmbedTextEmbedder
from app.retrieval.contracts import KnowledgeRetriever
from app.retrieval.hybrid_retriever import (
    HybridKnowledgeRetriever,
    UnavailableKnowledgeRetriever,
    load_index_manifest,
)
from app.retrieval.manifest import IndexManifest


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    """提供进程内共享锁的会话 JSON 仓库。"""
    return ConversationRepository(CONVERSATIONS_PATH)


@lru_cache
def get_versioned_llm_client() -> LLMClient:
    """提供新版聊天与压缩共用的异步 LLM 客户端。"""
    return LLMClient(llm_model)


@lru_cache
def get_performance_recorder() -> CsvPerformanceRecorder:
    """提供聊天主流程和只读页面共用的性能记录器。"""
    return CsvPerformanceRecorder(PERFORMANCE_METRICS_PATH)


@lru_cache
def get_versioned_chat_service() -> VersionedChatService:
    """组装版本化 Context 与 Turn 生命周期。"""
    repository = get_conversation_repository()
    llm_client = get_versioned_llm_client()
    context_builder = ContextBuilder(
        token_counter=TokenCounter(),
    )
    context_planner = ContextPlanner(
        context_builder=context_builder,
        high_watermark=CONTEXT_HIGH_WATERMARK,
        low_watermark=CONTEXT_LOW_WATERMARK,
        recent_raw_token_target=RECENT_RAW_TOKEN_TARGET,
    )
    compression_service = VersionedContextCompressionService(
        repository=repository,
        context_planner=context_planner,
        batch_planner=CompressionBatchPlanner(
            context_builder=context_builder,
            safety_margin=CONTEXT_SAFETY_MARGIN,
            min_summary_token_budget=SUMMARY_TOKEN_BUDGET,
        ),
        compressor=LLMCompressor(llm_client),
    )
    context_manager = VersionedContextManager(
        repository=repository,
        context_planner=context_planner,
        compression_service=compression_service,
        max_compression_passes=MAX_COMPRESSION_PASSES,
    )
    return VersionedChatService(
        repository=repository,
        llm_client=llm_client,
        context_manager=context_manager,
        performance_sink=get_performance_recorder(),
    )


@lru_cache
def get_conversation_service() -> ConversationService:
    """提供会话、历史、重写与分支操作的应用服务。"""
    repository = get_conversation_repository()
    return ConversationService(
        repository=repository,
        branch_service=BranchService(repository),
        chat_service=get_versioned_chat_service(),
    )


@lru_cache
def get_knowledge_index_manifest() -> IndexManifest | None:
    """读取已部署公共知识库的版本与规模。"""
    return load_index_manifest(KNOWLEDGE_BASE_INDEX_PATH)


@lru_cache
def get_knowledge_retriever() -> KnowledgeRetriever:
    """组装只读混合检索器；索引缺失时返回显式空实现。"""
    manifest = get_knowledge_index_manifest()
    if manifest is None:
        return UnavailableKnowledgeRetriever()
    return HybridKnowledgeRetriever.from_directory(
        KNOWLEDGE_BASE_INDEX_PATH,
        embedder=FastEmbedTextEmbedder(
            model_name=manifest.embedding_model,
            dimension=manifest.embedding_dimension,
        ),
    )


@lru_cache
def get_learning_turn_orchestrator() -> LearningTurnOrchestrator:
    """组装无状态学习问答的完整应用服务。"""
    return LearningTurnOrchestrator(
        graph_adapter=CompactGraphAdapter(),
        graph_policy=LearningGraphPolicy(),
        path_validator=ActivePathValidator(),
        context_service=LearningContextService(
            token_estimator=TokenCounter(),
            safety_margin=CONTEXT_SAFETY_MARGIN,
        ),
        model_factory=RuntimeLLMFactory(),
        knowledge_retriever=get_knowledge_retriever(),
        observer=LoggingLearningObserver(),
    )
