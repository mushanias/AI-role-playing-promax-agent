"""对话路由：POST /chat"""

from fastapi import APIRouter, Depends

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.core.dependencies import get_chat_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """对话接口：接收用户消息，返回 AI 回复"""
    reply = chat_service.send(request.message)
    return ChatResponse(reply=reply)