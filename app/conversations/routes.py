"""版本化会话、后台增量生成、原文历史与会话分支 HTTP 接口。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.auth import require_local_user
from app.core.dependencies import (
    get_conversation_service,
    get_generation_registry,
)
from app.core.error_mapping import map_app_exception
from app.exceptions import BaseAppException
from app.conversations.chat_stream import ChatStreamEvent
from app.conversations.chat_turn import ChatTurnResult
from app.conversations.conversation_service import ConversationService
from app.conversations.conversation_view import ConversationHistory
from app.conversations.generation_registry import (
    GenerationControl,
    GenerationRegistry,
    GenerationSnapshot,
)
from app.conversations.schemas import (
    BranchActivationResponse,
    ChatTurnResponse,
    ConversationCreateResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
    ConversationSummaryResponse,
    DeletedConversationListResponse,
    DeletedConversationSummaryResponse,
    GenerationStartResponse,
    GenerationStatusResponse,
    HistoryTurnResponse,
    RewriteTurnRequest,
    SendTurnRequest,
    StartGenerationRequest,
    StartRewriteGenerationRequest,
    TurnVariantResponse,
    TurnVariantsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_local_user)],
)

generations_router = APIRouter(
    prefix="/generations",
    tags=["generations"],
    dependencies=[Depends(require_local_user)],
)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    summaries = await service.list_conversations()
    return ConversationListResponse(
        conversations=[
            ConversationSummaryResponse(
                conversation_id=summary.conversation_id,
                title=summary.title,
                updated_at=summary.updated_at,
            )
            for summary in summaries
        ]
    )


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
    "/trash",
    response_model=DeletedConversationListResponse,
)
async def list_deleted_conversations(
    service: ConversationService = Depends(get_conversation_service),
) -> DeletedConversationListResponse:
    summaries = await service.list_deleted_conversations()
    return DeletedConversationListResponse(
        conversations=[
            DeletedConversationSummaryResponse(
                conversation_id=summary.conversation_id,
                title=summary.title,
                deleted_at=summary.deleted_at,
            )
            for summary in summaries
        ]
    )


@router.post(
    "/trash/{conversation_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> Response:
    await service.restore_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> Response:
    await service.delete_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    "/{conversation_id}/turns/generations",
    response_model=GenerationStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_turn_generation(
    conversation_id: str,
    generation_request: StartGenerationRequest,
    service: ConversationService = Depends(get_conversation_service),
    registry: GenerationRegistry = Depends(get_generation_registry),
) -> GenerationStartResponse:
    control = await registry.register(
        generation_request.generation_id,
        conversation_id,
    )
    events = service.stream_message(
        conversation_id=conversation_id,
        user_input=generation_request.message,
        generation_id=generation_request.generation_id,
        stop_event=control.stop_event,
        branch_id=generation_request.branch_id,
    )
    await _start_background_generation(
        events=events,
        control=control,
        registry=registry,
    )
    return GenerationStartResponse(
        generation_id=generation_request.generation_id,
        status="starting",
    )


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


@router.post(
    "/{conversation_id}/turns/{turn_id}/rewrite/generations",
    response_model=GenerationStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_rewrite_generation(
    conversation_id: str,
    turn_id: str,
    generation_request: StartRewriteGenerationRequest,
    service: ConversationService = Depends(get_conversation_service),
    registry: GenerationRegistry = Depends(get_generation_registry),
) -> GenerationStartResponse:
    control = await registry.register(
        generation_request.generation_id,
        conversation_id,
    )
    events = service.stream_rewrite_turn(
        conversation_id=conversation_id,
        target_turn_id=turn_id,
        user_input=generation_request.message,
        generation_id=generation_request.generation_id,
        stop_event=control.stop_event,
        source_branch_id=generation_request.source_branch_id,
    )
    await _start_background_generation(
        events=events,
        control=control,
        registry=registry,
    )
    return GenerationStartResponse(
        generation_id=generation_request.generation_id,
        status="starting",
    )


@generations_router.post(
    "/{generation_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_generation(
    generation_id: str,
    registry: GenerationRegistry = Depends(get_generation_registry),
) -> Response:
    """幂等地停止当前进程内的一次流式生成。"""
    await registry.request_stop(generation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@generations_router.get(
    "/{generation_id}",
    response_model=GenerationStatusResponse,
)
async def get_generation_status(
    generation_id: str,
    registry: GenerationRegistry = Depends(get_generation_registry),
) -> GenerationStatusResponse:
    snapshot = await registry.get_snapshot(generation_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="生成任务不存在或已过期",
        )
    return _generation_status_response(snapshot)


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
                response_duration_ms=turn.response_duration_ms,
                failure_message=turn.failure_message,
                finish_reason=turn.finish_reason,
                variant_index=turn.variant_index,
                variant_count=turn.variant_count,
                has_variants=(turn.variant_count > 1),
            )
            for turn in history.turns
        ],
    )


async def _start_background_generation(
    *,
    events: AsyncIterator[ChatStreamEvent],
    control: GenerationControl,
    registry: GenerationRegistry,
) -> None:
    task = asyncio.create_task(
        _consume_generation_events(
            events=events,
            control=control,
            registry=registry,
        )
    )
    await registry.attach_task(control.generation_id, control, task)


async def _consume_generation_events(
    *,
    events: AsyncIterator[ChatStreamEvent],
    control: GenerationControl,
    registry: GenerationRegistry,
) -> None:
    terminal_received = False
    try:
        async for event in events:
            await registry.apply_event(
                control.generation_id,
                control,
                event,
            )
            if event.type in {"completed", "stopped"}:
                terminal_received = True

        if not terminal_received:
            await registry.mark_failed(
                control.generation_id,
                control,
                code="incomplete_generation",
                message="生成任务未返回完成状态",
                status=status.HTTP_502_BAD_GATEWAY,
            )
    except BaseAppException as error:
        descriptor = map_app_exception(error)
        await registry.mark_failed(
            control.generation_id,
            control,
            code=descriptor.code,
            message=descriptor.message,
            status=descriptor.status_code,
        )
    except asyncio.CancelledError:
        control.request_stop()
        await registry.mark_failed(
            control.generation_id,
            control,
            code="generation_interrupted",
            message="生成任务因服务停止而中断",
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        raise
    except Exception:
        logger.exception(
            "后台生成发生未处理异常：generation=%s",
            control.generation_id,
        )
        await registry.mark_failed(
            control.generation_id,
            control,
            code="internal_server_error",
            message="后端处理生成任务时发生内部错误",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        await registry.finish_task(control.generation_id, control)


def _generation_status_response(
    snapshot: GenerationSnapshot,
) -> GenerationStatusResponse:
    return GenerationStatusResponse(
        generation_id=snapshot.generation_id,
        status=snapshot.status,
        conversation_id=snapshot.conversation_id,
        branch_id=snapshot.branch_id,
        turn_id=snapshot.turn_id,
        content=snapshot.content,
        duration_ms=snapshot.duration_ms,
        finish_reason=snapshot.finish_reason,
        warnings=list(snapshot.warnings),
        compression_passes=snapshot.compression_passes,
        quality_degraded=snapshot.quality_degraded,
        error_code=snapshot.error_code,
        error_message=snapshot.error_message,
        error_status=snapshot.error_status,
    )
