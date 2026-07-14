"""依赖提供者：集中管理 FastAPI 的依赖注入"""

from app.core.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    STORAGE_PATH, PROFILE_PATH,
)
from app.storage.json_storage import JsonStorage
from app.storage.profile_storage import ProfileStorage
from app.storage.context_state_storage import ContextStateStorage
from app.services.llm_client import LLMClient
from app.services.token_counter import TokenCounter
from app.services.context_builder import ContextBuilder
from app.services.chat_service import ChatService

# ContextStateStorage 的基础目录
CONTEXT_STATE_DIR = "data/context_states"


def get_token_counter() -> TokenCounter:
    """提供 TokenCounter 实例"""
    return TokenCounter(DEEPSEEK_MODEL)


def get_context_state_storage() -> ContextStateStorage:
    """提供 ContextStateStorage 实例"""
    return ContextStateStorage(CONTEXT_STATE_DIR)


def get_context_builder() -> ContextBuilder:
    """提供 ContextBuilder 实例"""
    return ContextBuilder(
        token_counter=get_token_counter(),
        message_storage=JsonStorage(STORAGE_PATH),
        profile_storage=ProfileStorage(PROFILE_PATH),
        state_storage=get_context_state_storage(),
        llm_client=LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL),
        model=DEEPSEEK_MODEL,
    )


def get_chat_service() -> ChatService:
    """提供 ChatService 实例"""
    storage = JsonStorage(STORAGE_PATH)
    llm_client = LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    context_builder = get_context_builder()
    return ChatService(storage, llm_client, context_builder)


def get_profile_storage() -> ProfileStorage:
    """提供 ProfileStorage 实例"""
    return ProfileStorage(PROFILE_PATH)
