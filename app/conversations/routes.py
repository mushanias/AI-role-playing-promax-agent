"""版本化会话、原文历史、流式回答与会话分支 HTTP 接口。"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse

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
    HistoryTurnResponse,
    RewriteTurnRequest,
    SendTurnRequest,
    StreamRewriteTurnRequest,
    StreamSendTurnRequest,
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


@router.post("/{conversation_id}/turns/stream")
async def stream_turn(
    conversation_id: str,
    stream_request: StreamSendTurnRequest,
    request: Request,
    service: ConversationService = Depends(get_conversation_service),
    registry: GenerationRegistry = Depends(get_generation_registry),
) -> StreamingResponse:
    control = await registry.register(stream_request.generation_id)
    events = service.stream_message(
        conversation_id=conversation_id,
        user_input=stream_request.message,
        generation_id=stream_request.generation_id,
        stop_event=control.stop_event,
        branch_id=stream_request.branch_id,
    )
    return _streaming_response(
        request=request,
        events=events,
        control=control,
        registry=registry,
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


@router.post("/{conversation_id}/turns/{turn_id}/rewrite/stream")
async def stream_rewrite_turn(
    conversation_id: str,
    turn_id: str,
    stream_request: StreamRewriteTurnRequest,
    request: Request,
    service: ConversationService = Depends(get_conversation_service),
    registry: GenerationRegistry = Depends(get_generation_registry),
) -> StreamingResponse:
    control = await registry.register(stream_request.generation_id)
    events = service.stream_rewrite_turn(
        conversation_id=conversation_id,
        target_turn_id=turn_id,
        user_input=stream_request.message,
        generation_id=stream_request.generation_id,
        stop_event=control.stop_event,
        source_branch_id=stream_request.source_branch_id,
    )
    return _streaming_response(
        request=request,
        events=events,
        control=control,
        registry=registry,
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


def _streaming_response(
    *,
    request: Request,
    events: AsyncIterator[ChatStreamEvent],
    control: GenerationControl,
    registry: GenerationRegistry,
) -> StreamingResponse:
    return StreamingResponse(
        _stream_sse_events(
            request=request,
            events=events,
            control=control,
            registry=registry,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_sse_events(
    *,
    request: Request,
    events: AsyncIterator[ChatStreamEvent],
    control: GenerationControl,
    registry: GenerationRegistry,
) -> AsyncIterator[str]:
    disconnect_watcher = asyncio.create_task(
        _watch_disconnect(request, control)
    )
    try:
        async for event in events:
            yield _encode_sse(event.type, _event_payload(event))
    except BaseAppException as error:
        descriptor = map_app_exception(error)
        yield _encode_sse(
            "failed",
            {
                "generation_id": control.generation_id,
                "code": descriptor.code,
                "message": descriptor.message,
                "status": descriptor.status_code,
            },
        )
    except asyncio.CancelledError:
        control.request_stop()
        raise
    except Exception:
        logger.exception(
            "流式生成发生未处理异常：generation=%s",
            control.generation_id,
        )
        yield _encode_sse(
            "failed",
            {
                "generation_id": control.generation_id,
                "code": "internal_server_error",
                "message": "后端处理流式回答时发生内部错误",
                "status": 500,
            },
        )
    finally:
        disconnect_watcher.cancel()
        with suppress(asyncio.CancelledError):
            await disconnect_watcher
        await registry.release(control.generation_id, control)


async def _watch_disconnect(
    request: Request,
    control: GenerationControl,
) -> None:
    while not control.stop_event.is_set():
        if await request.is_disconnected():
            control.request_stop()
            return
        await asyncio.sleep(0.1)


def _event_payload(event: ChatStreamEvent) -> dict[str, object]:
    payload: dict[str, object] = {
        "generation_id": event.generation_id,
        "conversation_id": event.conversation_id,
        "branch_id": event.branch_id,
        "turn_id": event.turn_id,
    }
    if event.content is not None:
        payload["content"] = event.content
    if event.duration_ms is not None:
        payload["duration_ms"] = event.duration_ms
    if event.type in {"completed", "stopped"}:
        payload["finish_reason"] = event.type
        payload["warnings"] = list(event.warnings)
        payload["compression_passes"] = event.compression_passes
        payload["quality_degraded"] = event.quality_degraded
    return payload


def _encode_sse(event: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"
