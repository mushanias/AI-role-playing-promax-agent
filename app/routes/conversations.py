"""版本化会话、原文历史与剧情分支 HTTP 接口。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_conversation_service
from app.models.chat_turn import ChatTurnResult
from app.models.conversation_view import ConversationHistory
from app.schemas.conversation import (
    BranchActivationResponse,
    ChatTurnResponse,
    ConversationCreateResponse,
    ConversationHistoryResponse,
    HistoryTurnResponse,
    RewriteTurnRequest,
    SendTurnRequest,
    TurnVariantResponse,
    TurnVariantsResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "",
    response_model=ConversationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationCreateResponse:
    conversation = await service.create_conversation()
    return ConversationCreateResponse(
        conversation_id=conversation.conversation_id,
        active_branch_id=conversation.active_branch_id,
    )


@router.get(
    "/{conversation_id}/history",
    response_model=ConversationHistoryResponse,
)
async def get_conversation_history(
    conversation_id: str,
    branch_id: Optional[str] = Query(default=None),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationHistoryResponse:
    history = await service.get_history(conversation_id, branch_id)
    return _history_response(history)


@router.post(
    "/{conversation_id}/turns",
    response_model=ChatTurnResponse,
)
async def send_turn(
    conversation_id: str,
    request: SendTurnRequest,
    service: ConversationService = Depends(get_conversation_service),
) -> ChatTurnResponse:
    result = await service.send_message(
        conversation_id=conversation_id,
        user_input=request.message,
        branch_id=request.branch_id,
    )
    return _chat_turn_response(result)


@router.post(
    "/{conversation_id}/turns/{turn_id}/rewrite",
    response_model=ChatTurnResponse,
)
async def rewrite_turn(
    conversation_id: str,
    turn_id: str,
    request: RewriteTurnRequest,
    service: ConversationService = Depends(get_conversation_service),
) -> ChatTurnResponse:
    result = await service.rewrite_turn(
        conversation_id=conversation_id,
        target_turn_id=turn_id,
        user_input=request.message,
        source_branch_id=request.source_branch_id,
    )
    return _chat_turn_response(result)


@router.get(
    "/{conversation_id}/turns/{turn_id}/variants",
    response_model=TurnVariantsResponse,
)
async def get_turn_variants(
    conversation_id: str,
    turn_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> TurnVariantsResponse:
    variants = await service.list_turn_variants(
        conversation_id,
        turn_id,
    )
    return TurnVariantsResponse(
        variants=[
            TurnVariantResponse(
                turn_id=variant.turn_id,
                branch_id=variant.branch_id,
                user_content=variant.user_content,
                created_at=variant.created_at,
                is_active=variant.is_active,
            )
            for variant in variants
        ]
    )


@router.post(
    "/{conversation_id}/branches/{branch_id}/activate",
    response_model=BranchActivationResponse,
)
async def activate_branch(
    conversation_id: str,
    branch_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> BranchActivationResponse:
    branch = await service.activate_branch(conversation_id, branch_id)
    return BranchActivationResponse(
        conversation_id=conversation_id,
        active_branch_id=branch.branch_id,
        head_turn_id=branch.head_turn_id,
        active_summary_id=branch.active_summary_id,
    )


def _chat_turn_response(result: ChatTurnResult) -> ChatTurnResponse:
    return ChatTurnResponse(
        conversation_id=result.conversation_id,
        branch_id=result.branch_id,
        turn_id=result.turn_id,
        reply=result.reply,
        warnings=list(result.warnings),
        compression_passes=result.compression_passes,
        quality_degraded=result.quality_degraded,
    )


def _history_response(
    history: ConversationHistory,
) -> ConversationHistoryResponse:
    return ConversationHistoryResponse(
        conversation_id=history.conversation_id,
        branch_id=history.branch_id,
        active_branch_id=history.active_branch_id,
        turns=[
            HistoryTurnResponse(
                turn_id=turn.turn_id,
                parent_turn_id=turn.parent_turn_id,
                user_content=turn.user_content,
                assistant_content=turn.assistant_content,
                status=turn.status,
                created_at=turn.created_at,
                completed_at=turn.completed_at,
                variant_index=turn.variant_index,
                variant_count=turn.variant_count,
                has_variants=(turn.variant_count > 1),
            )
            for turn in history.turns
        ],
    )
