from pydantic import BaseModel


class ChatRequest(BaseModel):
    """对话请求"""
    message: str          # 用户输入


class ChatResponse(BaseModel):
    """对话响应"""
    reply: str            # AI 回复