from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from app.services.llm_client import LLMClient

client = LLMClient(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    model=DEEPSEEK_MODEL
)

# 传入消息列表（只要 role 和 content）
reply = client.chat([
    {"role": "user", "content": "你好"}
])
print(reply)  # 助手的回复