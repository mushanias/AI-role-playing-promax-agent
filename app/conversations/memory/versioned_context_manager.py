"""读取分支 Context，并在主对话调用前完成同步压缩编排。"""

from typing import Dict, Optional, Protocol, Tuple

from app.context import ContextPrefixProvider, ContextPrefixRequest
from app.conversations.conversation_repository import ConversationRepository
from app.conversations.memory.compression_plan import VersionedCompressionOutcome
from app.conversations.memory.context_plan import (
    ContextCandidate,
    ContextPlan,
    ManagedContext,
)
from app.conversations.memory.context_planner import ContextPlanner


class VersionedCompressionCoordinator(Protocol):
    """新版 ContextManager 依赖的最小压缩接口。"""

    async def compress_if_needed(
        self,
        conversation_id: str,
        branch_id: str,
        prefix_messages: Tuple[Dict[str, str], ...] = (),
    ) -> VersionedCompressionOutcome:
        ...


class VersionedContextManager:
    """为指定会话分支生成最终 Context，并汇总降级警告。"""

    def __init__(
        self,
        repository: ConversationRepository,
        context_planner: ContextPlanner,
        compression_service: VersionedCompressionCoordinator,
        max_compression_passes: int,
        prefix_provider: Optional[ContextPrefixProvider] = None,
    ) -> None:
        if max_compression_passes < 1:
            raise ValueError("最大压缩次数必须大于 0")

        self.repository = repository
        self.context_planner = context_planner
        self.compression_service = compression_service
        self.max_compression_passes = max_compression_passes
        self.prefix_provider = prefix_provider

    async def build(
        self,
        conversation_id: str,
        branch_id: Optional[str] = None,
    ) -> ManagedContext:
        """同步压缩当前分支，并始终返回可继续处理的 Context。"""
        prefix_messages = await self._get_prefix_messages(
            conversation_id=conversation_id,
            branch_id=branch_id,
        )
        candidate = await self._build_candidate(
            conversation_id=conversation_id,
            branch_id=branch_id,
            prefix_messages=prefix_messages,
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
                    prefix_messages=prefix_messages,
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

        degraded_messages = None
        degraded_estimated_tokens = None
        if candidate.needs_compression:
            (
                degraded_messages,
                degraded_estimated_tokens,
                degradation_warning,
            ) = self._build_degraded_payload(candidate)
            self._append_warning(warnings, degradation_warning)

        return ManagedContext(
            candidate=candidate,
            warnings=tuple(warnings),
            compression_passes=compression_passes,
            degraded_messages=degraded_messages,
            degraded_estimated_tokens=degraded_estimated_tokens,
        )

    async def _build_candidate(
        self,
        conversation_id: str,
        branch_id: Optional[str],
        prefix_messages: Tuple[Dict[str, str], ...],
    ) -> ContextCandidate:
        conversation = await self.repository.load(conversation_id)
        return self.context_planner.build_candidate(
            conversation=conversation,
            branch_id=branch_id,
            prefix_messages=prefix_messages,
        )

    async def _get_prefix_messages(
        self,
        conversation_id: str,
        branch_id: Optional[str],
    ) -> Tuple[Dict[str, str], ...]:
        if self.prefix_provider is None:
            return ()
        return await self.prefix_provider.get_messages(
            ContextPrefixRequest(
                conversation_id=conversation_id,
                branch_id=branch_id,
            )
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

    def _build_degraded_payload(
        self,
        candidate: ContextCandidate,
    ) -> tuple[tuple[Dict[str, str], ...], int, str]:
        """只缩减本次发送副本，不修改原始 Turn 或摘要。"""
        plan = candidate.plan
        raw_turns = plan.raw_turns

        for drop_count in range(1, len(raw_turns) + 1):
            degraded = self.context_planner.context_builder.build_from_plan(
                plan=ContextPlan(
                    conversation_id=plan.conversation_id,
                    branch_id=plan.branch_id,
                    summary=plan.summary,
                    raw_turns=raw_turns[drop_count:],
                    pending_turn=plan.pending_turn,
                    prefix_messages=plan.prefix_messages,
                ),
            )
            if degraded.estimated_tokens <= candidate.high_watermark:
                return (
                    degraded.messages,
                    degraded.estimated_tokens,
                    "本轮发送载荷已省略较早原文；JSON 中的完整历史未修改。",
                )

        without_summary = (
            self.context_planner.context_builder.build_from_plan(
                plan=ContextPlan(
                    conversation_id=plan.conversation_id,
                    branch_id=plan.branch_id,
                    summary=None,
                    raw_turns=(),
                    pending_turn=plan.pending_turn,
                    prefix_messages=plan.prefix_messages,
                ),
            )
        )
        if without_summary.estimated_tokens <= candidate.high_watermark:
            return (
                without_summary.messages,
                without_summary.estimated_tokens,
                "本轮发送载荷已省略历史摘要与较早原文；持久化历史未修改。",
            )

        hard_limited = self._hard_limit_payload(
            messages=without_summary.messages,
            token_limit=candidate.high_watermark,
        )
        return (
            hard_limited[0],
            hard_limited[1],
            "当前输入极端过长，本轮发送副本已截短；原始数据仍完整保留。",
        )

    def _hard_limit_payload(
        self,
        messages: tuple[Dict[str, str], ...],
        token_limit: int,
    ) -> tuple[tuple[Dict[str, str], ...], int]:
        """优先保留当前用户输入，再用剩余空间保留历史摘要。"""
        current_user = next(
            (
                message
                for message in reversed(messages)
                if message["role"] == "user"
            ),
            None,
        )
        system_message = next(
            (
                message
                for message in messages
                if message["role"] == "system"
            ),
            None,
        )
        if current_user is None:
            if system_message is None:
                return (), 0
            limited_system = self._truncate_message_to_fit(
                message=system_message,
                companion_messages=(),
                token_limit=token_limit,
            )
            result = (limited_system,)
            return result, self._count_messages(result)

        user_only = (dict(current_user),)
        user_tokens = self._count_messages(user_only)

        if user_tokens > token_limit:
            limited_user = self._truncate_message_to_fit(
                message=current_user,
                companion_messages=(),
                token_limit=token_limit,
            )
            result = (limited_user,)
            return result, self._count_messages(result)

        if system_message is None:
            return user_only, user_tokens

        limited_system = self._truncate_message_to_fit(
            message=system_message,
            companion_messages=user_only,
            token_limit=token_limit,
        )
        result = (limited_system, *user_only)
        estimated_tokens = self._count_messages(result)
        if estimated_tokens > token_limit:
            return user_only, user_tokens
        return result, estimated_tokens

    def _truncate_message_to_fit(
        self,
        message: Dict[str, str],
        companion_messages: tuple[Dict[str, str], ...],
        token_limit: int,
    ) -> Dict[str, str]:
        marker = "\n\n【内容因长度限制已截短】\n\n"
        content = message["content"]
        low = 0
        high = len(content)
        best = ""

        while low <= high:
            keep = (low + high) // 2
            candidate_content = self._keep_content_edges(
                content,
                keep,
                marker,
            )
            candidate_message = {
                "role": message["role"],
                "content": candidate_content,
            }
            candidate_messages = (
                candidate_message,
                *companion_messages,
            )
            if self._count_messages(candidate_messages) <= token_limit:
                best = candidate_content
                low = keep + 1
            else:
                high = keep - 1

        return {"role": message["role"], "content": best}

    def _count_messages(
        self,
        messages: tuple[Dict[str, str], ...],
    ) -> int:
        return self.context_planner.context_builder.token_counter.count_messages(
            messages
        )

    @staticmethod
    def _keep_content_edges(
        content: str,
        keep: int,
        marker: str,
    ) -> str:
        if keep >= len(content):
            return content
        if keep <= 0:
            return marker.strip()

        prefix_size = (keep + 1) // 2
        suffix_size = keep // 2
        suffix = content[-suffix_size:] if suffix_size else ""
        return f"{content[:prefix_size]}{marker}{suffix}"

    @staticmethod
    def _append_warning(
        warnings: list[str],
        warning: Optional[str],
    ) -> None:
        if warning and warning not in warnings:
            warnings.append(warning)
