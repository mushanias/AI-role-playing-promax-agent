"""依赖提供者：集中管理 FastAPI 的依赖注入。"""

from functools import lru_cache

from app.core.config import (
    CONTEXT_HIGH_WATERMARK,
    CONTEXT_LOW_WATERMARK,
    CONTEXT_SAFETY_MARGIN,
    CONVERSATIONS_PATH,
    MAX_COMPRESSION_PASSES,
    PROFILE_PATH,
    RECENT_RAW_TOKEN_TARGET,
    SUMMARY_TOKEN_BUDGET,
)
from app.llm import llm_model
from app.services.branch_service import BranchService
from app.services.conversation_service import ConversationService
from app.services.context_builder import ContextBuilder
from app.services.context_planner import ContextPlanner
from app.services.llm_compressor import LLMCompressor
from app.services.token_counter import TokenCounter
from app.services.versioned_chat_service import VersionedChatService
from app.services.versioned_context_compression_service import (
    CompressionBatchPlanner,
    VersionedContextCompressionService,
)
from app.services.versioned_context_manager import VersionedContextManager
from app.storage.conversation_repository import ConversationRepository
from app.storage.profile_storage import ProfileStorage
from app.services.llm_client import LLMClient


@lru_cache
def get_profile_storage() -> ProfileStorage:
    """提供 ProfileStorage 实例"""
    return ProfileStorage(PROFILE_PATH)


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    """提供进程内共享锁的会话 JSON 仓库。"""
    return ConversationRepository(CONVERSATIONS_PATH)


@lru_cache
def get_versioned_llm_client() -> LLMClient:
    """提供新版聊天与压缩共用的异步 LLM 客户端。"""
    return LLMClient(llm_model)


@lru_cache
def get_versioned_chat_service() -> VersionedChatService:
    """组装版本化 Context 与 Turn 生命周期。"""
    repository = get_conversation_repository()
    profile_storage = get_profile_storage()
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
        profile_storage=profile_storage,
        context_planner=context_planner,
        compression_service=compression_service,
        max_compression_passes=MAX_COMPRESSION_PASSES,
    )
    return VersionedChatService(
        repository=repository,
        llm_client=llm_client,
        context_manager=context_manager,
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
