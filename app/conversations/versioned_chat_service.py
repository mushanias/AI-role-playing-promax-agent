"""按 Turn 生命周期编排分支 Context、主 LLM 与原文持久化。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime, timezone
from time import perf_counter
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from app.exceptions import (
    BranchNotFoundError,
    InvalidBranchOperationError,
    TurnNotFoundError,
)
from app.conversations.chat_stream import ChatStreamEvent
from app.conversations.chat_turn import ChatTurnResult
from app.conversations.conversation import (
    Conversation,
    Turn,
    TurnFinishReason,
    TurnStatus,
)
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.memory.context_plan import ManagedContext
from app.performance.recorder import PerformanceSink

logger = logging.getLogger(__name__)


class ManagedContextBuilder(Protocol):
    """新版 ChatService 依赖的最小 ContextManager 接口。"""

    async def build(
        self,
        conversation_id: str,
        branch_id: Optional[str] = None,
    ) -> ManagedContext:
        ...


class ChatLLMClient(Protocol):
    """新版 ChatService 依赖的最小主对话 LLM 接口。"""

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        ...

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncIterator[str]:
        ...


class VersionedChatService:
    """创建 pending Turn，调用 LLM，并提交 completed/failed 状态。"""

    def __init__(
        self,
        repository: ConversationRepository,
        llm_client: ChatLLMClient,
        context_manager: ManagedContextBuilder,
        performance_sink: Optional[PerformanceSink] = None,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.context_manager = context_manager
        self.performance_sink = performance_sink

    async def send(
        self,
        conversation_id: str,
        user_input: str,
        branch_id: Optional[str] = None,
    ) -> ChatTurnResult:
        """在指定分支上完成一次用户输入与助手回复。"""
        request_started = perf_counter()
        turn_id = str(uuid4())
        selected_branch_id = await self._create_pending_turn(
            conversation_id=conversation_id,
            branch_id=branch_id,
            turn_id=turn_id,
            user_input=user_input,
        )

        try:
            context_started = perf_counter()
            context = await self.context_manager.build(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
            )
            context_ms = self._elapsed_ms(context_started)

            llm_started = perf_counter()
            reply = await self.llm_client.chat(list(context.messages))
            llm_ms = self._elapsed_ms(llm_started)
            response_duration_ms = round(self._elapsed_ms(request_started))
            await self._complete_turn(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                turn_id=turn_id,
                reply=reply,
                response_duration_ms=response_duration_ms,
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                self._mark_turn_failed_safely(
                    conversation_id=conversation_id,
                    branch_id=selected_branch_id,
                    turn_id=turn_id,
                    failure_message="请求已取消",
                )
            )
            raise
        except Exception as error:
            await self._mark_turn_failed_safely(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                turn_id=turn_id,
                failure_message=self._describe_failure(error),
            )
            raise

        total_ms = self._elapsed_ms(request_started)
        await self._record_performance_safely(
            conversation_id=conversation_id,
            branch_id=selected_branch_id,
            total_ms=total_ms,
            context_ms=context_ms,
            llm_ms=llm_ms,
            input_tokens=context.estimated_tokens,
            compression_passes=context.compression_passes,
            quality_degraded=context.quality_degraded,
        )

        return ChatTurnResult(
            conversation_id=conversation_id,
            branch_id=selected_branch_id,
            turn_id=turn_id,
            reply=reply,
            warnings=context.warnings,
            compression_passes=context.compression_passes,
            quality_degraded=context.quality_degraded,
        )

    async def stream(
        self,
        conversation_id: str,
        user_input: str,
        generation_id: str,
        stop_event: asyncio.Event,
        branch_id: Optional[str] = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """持久化 pending Turn，并把模型文本逐段转换为领域事件。"""
        request_started = perf_counter()
        turn_id = str(uuid4())
        reply_parts: list[str] = []
        finalized = False
        context_ms = 0.0
        llm_ms = 0.0
        input_tokens = 0
        warnings: tuple[str, ...] = ()
        compression_passes = 0
        quality_degraded = False
        selected_branch_id = await self._create_pending_turn(
            conversation_id=conversation_id,
            branch_id=branch_id,
            turn_id=turn_id,
            user_input=user_input,
        )

        yield ChatStreamEvent(
            type="started",
            generation_id=generation_id,
            conversation_id=conversation_id,
            branch_id=selected_branch_id,
            turn_id=turn_id,
        )

        try:
            if not stop_event.is_set():
                context_started = perf_counter()
                context = await self.context_manager.build(
                    conversation_id=conversation_id,
                    branch_id=selected_branch_id,
                )
                context_ms = self._elapsed_ms(context_started)
                input_tokens = context.estimated_tokens
                warnings = context.warnings
                compression_passes = context.compression_passes
                quality_degraded = context.quality_degraded

                llm_started = perf_counter()
                async for content in self._stream_until_stopped(
                    self.llm_client.stream_chat(list(context.messages)),
                    stop_event,
                ):
                    reply_parts.append(content)
                    yield ChatStreamEvent(
                        type="delta",
                        generation_id=generation_id,
                        conversation_id=conversation_id,
                        branch_id=selected_branch_id,
                        turn_id=turn_id,
                        content=content,
                    )
                llm_ms = self._elapsed_ms(llm_started)

            response_duration_ms = round(
                self._elapsed_ms(request_started)
            )
            finish_reason = (
                TurnFinishReason.STOPPED
                if stop_event.is_set()
                else TurnFinishReason.COMPLETED
            )
            await self._complete_turn(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                turn_id=turn_id,
                reply="".join(reply_parts),
                response_duration_ms=response_duration_ms,
                finish_reason=finish_reason,
            )
            finalized = True

            await self._record_performance_safely(
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                total_ms=self._elapsed_ms(request_started),
                context_ms=context_ms,
                llm_ms=llm_ms,
                input_tokens=input_tokens,
                compression_passes=compression_passes,
                quality_degraded=quality_degraded,
            )

            yield ChatStreamEvent(
                type=(
                    "stopped"
                    if finish_reason == TurnFinishReason.STOPPED
                    else "completed"
                ),
                generation_id=generation_id,
                conversation_id=conversation_id,
                branch_id=selected_branch_id,
                turn_id=turn_id,
                duration_ms=response_duration_ms,
                warnings=warnings,
                compression_passes=compression_passes,
                quality_degraded=quality_degraded,
            )
        except asyncio.CancelledError:
            stop_event.set()
            if not finalized:
                await asyncio.shield(
                    self._complete_turn(
                        conversation_id=conversation_id,
                        branch_id=selected_branch_id,
                        turn_id=turn_id,
                        reply="".join(reply_parts),
                        response_duration_ms=round(
                            self._elapsed_ms(request_started)
                        ),
                        finish_reason=TurnFinishReason.STOPPED,
                    )
                )
            raise
        except Exception as error:
            if not finalized:
                await self._mark_turn_failed_safely(
                    conversation_id=conversation_id,
                    branch_id=selected_branch_id,
                    turn_id=turn_id,
                    failure_message=self._describe_failure(error),
                )
            raise

    @staticmethod
    async def _stream_until_stopped(
        stream: AsyncIterator[str],
        stop_event: asyncio.Event,
    ) -> AsyncIterator[str]:
        """在等待下一个分片时同时监听停止信号。"""
        iterator = stream.__aiter__()

        try:
            while not stop_event.is_set():
                next_task = asyncio.create_task(anext(iterator))
                stop_task = asyncio.create_task(stop_event.wait())
                done, _ = await asyncio.wait(
                    {next_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if next_task in done:
                    stop_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await stop_task
                    try:
                        yield next_task.result()
                    except StopAsyncIteration:
                        return
                    continue

                next_task.cancel()
                with suppress(asyncio.CancelledError, StopAsyncIteration):
                    await next_task
                return
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                with suppress(RuntimeError):
                    await close()

    async def _record_performance_safely(
        self,
        *,
        conversation_id: str,
        branch_id: str,
        total_ms: float,
        context_ms: float,
        llm_ms: float,
        input_tokens: int,
        compression_passes: int,
        quality_degraded: bool,
    ) -> None:
        """记录失败只写日志，绝不改变已经成功的聊天结果。"""
        if self.performance_sink is None:
            return

        try:
            await self.performance_sink.record(
                conversation_id=conversation_id,
                branch_id=branch_id,
                total_ms=total_ms,
                context_ms=context_ms,
                llm_ms=llm_ms,
                input_tokens=input_tokens,
                compression_passes=compression_passes,
                quality_degraded=quality_degraded,
            )
        except Exception:
            logger.exception(
                "无法记录性能指标：conversation=%s branch=%s",
                conversation_id,
                branch_id,
            )

    async def _create_pending_turn(
        self,
        conversation_id: str,
        branch_id: Optional[str],
        turn_id: str,
        user_input: str,
    ) -> str:
        created_at = datetime.now(timezone.utc)

        def create(conversation: Conversation) -> Conversation:
            selected_branch_id = (
                branch_id or conversation.active_branch_id
            )
            branch = conversation.branches.get(selected_branch_id)
            if branch is None:
                raise BranchNotFoundError(
                    f"会话分支不存在：{selected_branch_id}"
                )
            if branch.pending_turn_id is not None:
                raise InvalidBranchOperationError(
                    "当前会话分支已有正在生成的轮次"
                )

            pending_turn = Turn(
                turn_id=turn_id,
                parent_turn_id=branch.head_turn_id,
                user_content=user_input,
                status=TurnStatus.PENDING,
                created_at=created_at,
            )
            conversation.turns[turn_id] = pending_turn
            branch.pending_turn_id = turn_id
            return conversation

        updated = await self.repository.update(conversation_id, create)
        for current_branch in updated.branches.values():
            if current_branch.pending_turn_id == turn_id:
                return current_branch.branch_id

        raise InvalidBranchOperationError(
            "pending Turn 已创建，但无法定位所属会话分支"
        )

    async def _complete_turn(
        self,
        conversation_id: str,
        branch_id: str,
        turn_id: str,
        reply: str,
        response_duration_ms: int,
        finish_reason: TurnFinishReason = TurnFinishReason.COMPLETED,
    ) -> None:
        completed_at = datetime.now(timezone.utc)

        def complete(conversation: Conversation) -> Conversation:
            branch = conversation.branches.get(branch_id)
            if branch is None:
                raise BranchNotFoundError(
                    f"会话分支不存在：{branch_id}"
                )
            turn = conversation.turns.get(turn_id)
            if turn is None:
                raise TurnNotFoundError(
                    f"原始轮次不存在：{turn_id}"
                )
            if (
                branch.pending_turn_id != turn_id
                or turn.status != TurnStatus.PENDING
            ):
                raise InvalidBranchOperationError(
                    "只能完成当前分支正在生成的轮次"
                )

            turn.assistant_content = reply
            turn.status = TurnStatus.COMPLETED
            turn.completed_at = completed_at
            turn.response_duration_ms = response_duration_ms
            turn.finish_reason = finish_reason
            branch.head_turn_id = turn_id
            branch.pending_turn_id = None
            return conversation

        await self.repository.update(conversation_id, complete)

    async def _mark_turn_failed_safely(
        self,
        conversation_id: str,
        branch_id: str,
        turn_id: str,
        failure_message: str,
    ) -> None:
        try:
            await self._mark_turn_failed(
                conversation_id=conversation_id,
                branch_id=branch_id,
                turn_id=turn_id,
                failure_message=failure_message,
            )
        except Exception:
            logger.exception(
                "无法保存 failed Turn：conversation=%s branch=%s turn=%s",
                conversation_id,
                branch_id,
                turn_id,
            )

    async def _mark_turn_failed(
        self,
        conversation_id: str,
        branch_id: str,
        turn_id: str,
        failure_message: str,
    ) -> None:
        def fail(conversation: Conversation) -> Conversation:
            branch = conversation.branches.get(branch_id)
            if branch is None:
                raise BranchNotFoundError(
                    f"会话分支不存在：{branch_id}"
                )
            turn = conversation.turns.get(turn_id)
            if turn is None:
                raise TurnNotFoundError(
                    f"原始轮次不存在：{turn_id}"
                )
            if (
                branch.pending_turn_id != turn_id
                or turn.status != TurnStatus.PENDING
            ):
                raise InvalidBranchOperationError(
                    "只能把当前分支正在生成的轮次标记为失败"
                )

            turn.status = TurnStatus.FAILED
            turn.failure_message = failure_message
            branch.failed_turn_ids.append(turn_id)
            branch.pending_turn_id = None
            return conversation

        await self.repository.update(conversation_id, fail)

    @staticmethod
    def _describe_failure(error: Exception) -> str:
        message = str(error).strip()
        if not message:
            return error.__class__.__name__
        return f"{error.__class__.__name__}: {message}"

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (perf_counter() - started_at) * 1000
