"""依赖提供者：集中管理 FastAPI 的依赖注入"""

from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, STORAGE_PATH
from app.storage.json_storage import JsonStorage
from app.services.llm_client import LLMClient
from app.services.chat_service import ChatService


def get_chat_service() -> ChatService:
    """提供 ChatService 实例
    将来想换实现（如换 SQLite、换 LLM、加缓存），只改这个函数，路由不动。
    """
    storage = JsonStorage(STORAGE_PATH)
    llm_client = LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    return ChatService(storage, llm_client)