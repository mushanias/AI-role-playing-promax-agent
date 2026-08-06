"""进程内生成任务注册表：保存停止信号、任务引用与可轮询状态。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal, Optional, Tuple

from app.conversations.chat_stream import ChatStreamEvent
from app.exceptions import InvalidBranchOperationError


GenerationStatus = Literal[
    "starting",
    "streaming",
    "completed",
    "stopped",
    "failed",
]
GenerationFinishReason = Literal["completed", "stopped"]
TERMINAL_GENERATION_STATUSES = frozenset(
    {"completed", "stopped", "failed"}
)


@dataclass(frozen=True)
class GenerationSnapshot:
    """提供给 HTTP 查询接口的生成状态快照。"""

    generation_id: str
    status: GenerationStatus
    conversation_id: str
    branch_id: Optional[str]
    turn_id: Optional[str]
    content: str
    duration_ms: Optional[int]
    finish_reason: Optional[GenerationFinishReason]
    warnings: Tuple[str, ...]
    compression_passes: int
    quality_degraded: bool
    error_code: Optional[str]
    error_message: Optional[str]
    error_status: Optional[int]


@dataclass
class GenerationControl:
    """单次后台生成任务的可变状态，仅允许注册表在锁内更新。"""

    generation_id: str
    conversation_id: str
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    status: GenerationStatus = "starting"
    branch_id: Optional[str] = None
    turn_id: Optional[str] = None
    content: str = ""
    duration_ms: Optional[int] = None
    finish_reason: Optional[GenerationFinishReason] = None
    warnings: Tuple[str, ...] = ()
    compression_passes: int = 0
    quality_degraded: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_status: Optional[int] = None
    task: Optional[asyncio.Task[None]] = field(default=None, repr=False)

    def request_stop(self) -> None:
        self.stop_event.set()

    def snapshot(self) -> GenerationSnapshot:
        return GenerationSnapshot(
            generation_id=self.generation_id,
            status=self.status,
            conversation_id=self.conversation_id,
            branch_id=self.branch_id,
            turn_id=self.turn_id,
            content=self.content,
            duration_ms=self.duration_ms,
            finish_reason=self.finish_reason,
            warnings=self.warnings,
            compression_passes=self.compression_passes,
            quality_degraded=self.quality_degraded,
            error_code=self.error_code,
            error_message=self.error_message,
            error_status=self.error_status,
        )


class GenerationRegistry:
    """保存后台任务，并为断线后的浏览器保留最近生成结果。"""

    def __init__(self, max_retained: int = 100) -> None:
        self._controls: dict[str, GenerationControl] = {}
        self._lock = asyncio.Lock()
        self._max_retained = max_retained

    async def register(
        self,
        generation_id: str,
        conversation_id: str,
    ) -> GenerationControl:
        async with self._lock:
            if generation_id in self._controls:
                raise InvalidBranchOperationError("生成任务 ID 已存在")
            self._prune_terminal_generations()
            control = GenerationControl(
                generation_id=generation_id,
                conversation_id=conversation_id,
            )
            self._controls[generation_id] = control
            return control

    async def attach_task(
        self,
        generation_id: str,
        control: GenerationControl,
        task: asyncio.Task[None],
    ) -> None:
        async with self._lock:
            if self._controls.get(generation_id) is control:
                control.task = task

    async def apply_event(
        self,
        generation_id: str,
        control: GenerationControl,
        event: ChatStreamEvent,
    ) -> None:
        async with self._lock:
            if self._controls.get(generation_id) is not control:
                return

            control.conversation_id = event.conversation_id
            control.branch_id = event.branch_id
            control.turn_id = event.turn_id

            if event.type == "started":
                control.status = "streaming"
            elif event.type == "delta":
                control.status = "streaming"
                control.content += event.content or ""
            elif event.type in {"completed", "stopped"}:
                control.status = event.type
                control.duration_ms = event.duration_ms
                control.finish_reason = event.type
                control.warnings = event.warnings
                control.compression_passes = event.compression_passes
                control.quality_degraded = event.quality_degraded

    async def mark_failed(
        self,
        generation_id: str,
        control: GenerationControl,
        *,
        code: str,
        message: str,
        status: int,
    ) -> None:
        async with self._lock:
            if self._controls.get(generation_id) is not control:
                return
            if control.status in TERMINAL_GENERATION_STATUSES:
                return
            control.status = "failed"
            control.error_code = code
            control.error_message = message
            control.error_status = status

    async def get_snapshot(
        self,
        generation_id: str,
    ) -> Optional[GenerationSnapshot]:
        async with self._lock:
            control = self._controls.get(generation_id)
            return control.snapshot() if control is not None else None

    async def request_stop(self, generation_id: str) -> bool:
        async with self._lock:
            control = self._controls.get(generation_id)
            if (
                control is None
                or control.status in TERMINAL_GENERATION_STATUSES
            ):
                return False
            control.request_stop()
            return True

    async def finish_task(
        self,
        generation_id: str,
        control: GenerationControl,
    ) -> None:
        async with self._lock:
            if self._controls.get(generation_id) is control:
                control.task = None

    def _prune_terminal_generations(self) -> None:
        while len(self._controls) >= self._max_retained:
            removable_id = next(
                (
                    generation_id
                    for generation_id, control in self._controls.items()
                    if control.status in TERMINAL_GENERATION_STATUSES
                    and control.task is None
                ),
                None,
            )
            if removable_id is None:
                return
            del self._controls[removable_id]
