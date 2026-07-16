"""依赖提供者：集中管理 FastAPI 的依赖注入"""

from app.core.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    STORAGE_PATH, PROFILE_PATH, CONTEXT_STATE_PATH, INPUT_TOKEN_BUDGET, RECENT_TURNS_KEEP, SUMMARY_TOKEN_BUDGET,
    MAX_COMPRESSION_PASSES,
)
from app.services.compression_batch_selector import CompressionBatchSelector
from app.services.context_builder import ContextBuilder
from app.services.context_compression_service import ContextCompressionService
from app.services.context_manager import ContextManager
from app.services.llm_compressor import LLMCompressor
from app.services.token_counter import TokenCounter
from app.storage.context_state_storage import ContextStateStorage
from app.storage.json_storage import JsonStorage
from app.storage.profile_storage import ProfileStorage
from app.services.llm_client import LLMClient
from app.services.chat_service import ChatService


def get_chat_service() -> ChatService:
    """提供 ChatService 实例"""
    storage = JsonStorage(STORAGE_PATH)
    profile_storage = ProfileStorage(PROFILE_PATH)
    state_storage = ContextStateStorage(CONTEXT_STATE_PATH)
    llm_client = LLMClient(
        DEEPSEEK_API_KEY,
        DEEPSEEK_BASE_URL,
        DEEPSEEK_MODEL,
    )

    context_builder = ContextBuilder(
        token_counter=TokenCounter(),
        input_token_budget=INPUT_TOKEN_BUDGET,
    )

    compression_service = ContextCompressionService(
        batch_selector=CompressionBatchSelector(
            RECENT_TURNS_KEEP,
        ),
        compressor=LLMCompressor(llm_client),
        summary_token_budget=SUMMARY_TOKEN_BUDGET,
    )

    context_manager = ContextManager(
        context_builder=context_builder,
        compression_service=compression_service,
        message_storage=storage,
        profile_storage=profile_storage,
        state_storage=state_storage,
        max_compression_passes=MAX_COMPRESSION_PASSES,
    )

    return ChatService(
        storage=storage,
        llm_client=llm_client,
        context_manager=context_manager,
    )


def get_profile_storage() -> ProfileStorage:
    """提供 ProfileStorage 实例"""
    return ProfileStorage(PROFILE_PATH)