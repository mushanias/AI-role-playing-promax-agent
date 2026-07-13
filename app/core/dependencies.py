"""依赖提供者：集中管理 FastAPI 的依赖注入"""

from app.core.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    STORAGE_PATH, PROFILE_PATH,
)
from app.storage.json_storage import JsonStorage
from app.storage.profile_storage import ProfileStorage
from app.services.llm_client import LLMClient
from app.services.chat_service import ChatService


def get_chat_service() -> ChatService:
    """提供 ChatService 实例"""
    storage = JsonStorage(STORAGE_PATH)
    llm_client = LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    profile_storage = ProfileStorage(PROFILE_PATH)
    return ChatService(storage, llm_client, profile_storage)


def get_profile_storage() -> ProfileStorage:
    """提供 ProfileStorage 实例"""
    return ProfileStorage(PROFILE_PATH)