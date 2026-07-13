from app.storage.json_storage import JsonStorage
from app.services.llm_client import LLMClient
from app.services.chat_service import ChatService
from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

# 组装依赖
storage = JsonStorage("data/chat_history.json")
llm_client = LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
chat = ChatService(storage, llm_client)

# 对话
reply = chat.send("你好")
print(reply)
