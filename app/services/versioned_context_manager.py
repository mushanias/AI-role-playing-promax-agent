"""读取分支 Context，并在主对话调用前完成同步压缩编排。"""

from typing import Dict, Optional, Protocol

from app.models.compression_plan import VersionedCompressionOutcome
from app.models.context_plan import ContextCandidate, ManagedContext
from app.services.context_planner import ContextPlanner
from app.storage.conversation_repository import ConversationRepository
from app.storage.profile_storage import ProfileStorage


class VersionedCompressionCoordinator(Protocol):
    """新版 ContextManager 依赖的最小压缩接口。"""

    async def compress_if_needed(
        self,
        conversation_id: str,
        branch_id: str,
        profile: Dict[str, str],
    ) -> VersionedCompressionOutcome:
        ...


class VersionedContextManager:
    """为指定会话分支生成最终 Context，并汇总降级警告。"""

    def __init__(
        self,
        repository: ConversationRepository,
        profile_storage: ProfileStorage,
        context_planner: ContextPlanner,
        compression_service: VersionedCompressionCoordinator,
        max_compression_passes: int,
    ) -> None:
        if max_compression_passes < 1:
            raise ValueError("最大压缩次数必须大于 0")

        self.repository = repository
        self.profile_storage = profile_storage
        self.context_planner = context_planner
        self.compression_service = compression_service
        self.max_compression_passes = max_compression_passes

    async def build(
        self,
        conversation_id: str,
        branch_id: Optional[str] = None,
    ) -> ManagedContext:
        """同步压缩当前分支，并始终返回可继续处理的 Context。"""
        profile = await self.profile_storage.load_profile()
        candidate = await self._build_candidate(
            conversation_id=conversation_id,
            branch_id=branch_id,
            profile=profile,
        )
        selected_branch_id = candidate.plan.branch_id
        warnings = []
        compression_passes = 0

        while (
            candidate.needs_compression
            and compression_passes < self.max_compression_passes
        ):
            outcome = (
                await self.compression_service.compress_if_needed(
                    conversation_id=conversation_id,
                    branch_id=selected_branch_id,
                    profile=profile,
                )
            )
            compression_passes += 1
            candidate = outcome.candidate
            self._append_warning(warnings, outcome.warning)

            if not outcome.compressed:
                break

        if candidate.needs_compression:
            self._append_warning(
                warnings,
                self._build_limit_warning(compression_passes),
            )

        return ManagedContext(
            candidate=candidate,
            warnings=tuple(warnings),
            compression_passes=compression_passes,
        )

    async def _build_candidate(
        self,
        conversation_id: str,
        branch_id: Optional[str],
        profile: Dict[str, str],
    ) -> ContextCandidate:
        conversation = await self.repository.load(conversation_id)
        return self.context_planner.build_candidate(
            conversation=conversation,
            profile=profile,
            branch_id=branch_id,
        )

    def _build_limit_warning(self, compression_passes: int) -> str:
        if compression_passes >= self.max_compression_passes:
            return (
                "上下文在达到本轮最大压缩次数后仍超过质量高水位；"
                "本轮将继续使用降级 Context。"
            )
        return (
            "上下文仍超过质量高水位；"
            "本轮将继续使用降级 Context。"
        )

    @staticmethod
    def _append_warning(
        warnings: list[str],
        warning: Optional[str],
    ) -> None:
        if warning and warning not in warnings:
            warnings.append(warning)
