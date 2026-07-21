"""按完整 Turn 执行追加式、分支安全的同步 Context 压缩。"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.exceptions import LLMResponseError
from app.models.compression_plan import (
    VersionedCompressionOutcome,
    VersionedCompressionPlan,
)
from app.models.context_plan import ContextCandidate, ContextPlan
from app.models.conversation import Conversation, SummaryVersion, Turn
from app.services.compressor import CompressionRequest, Compressor
from app.services.context_builder import ContextBuilder
from app.services.context_planner import ContextPlanner
from app.storage.conversation_repository import ConversationRepository


class CompressionBatchPlanner:
    """在完整 Turn 边界上选择最接近近期原文目标的压缩批次。"""

    def __init__(
        self,
        context_builder: ContextBuilder,
        safety_margin: int,
        min_summary_token_budget: int,
    ) -> None:
        if safety_margin < 0:
            raise ValueError("压缩安全余量不能小于 0")
        if min_summary_token_budget <= 0:
            raise ValueError("最小摘要 Token 预算必须大于 0")

        self.context_builder = context_builder
        self.safety_margin = safety_margin
        self.min_summary_token_budget = min_summary_token_budget

    def plan(
        self,
        candidate: ContextCandidate,
        profile: Dict[str, str],
    ) -> Optional[VersionedCompressionPlan]:
        """返回可达到低水位的最佳完整 Turn 压缩计划。"""
        if not candidate.needs_compression:
            return None

        raw_turns = candidate.plan.raw_turns
        if not raw_turns:
            return None

        feasible_plans: List[
            Tuple[int, int, VersionedCompressionPlan]
        ] = []

        for cutoff in range(1, len(raw_turns) + 1):
            turns_to_compress = raw_turns[:cutoff]
            raw_turns_to_keep = raw_turns[cutoff:]
            fixed_tokens = self._count_fixed_result_tokens(
                candidate=candidate,
                profile=profile,
                raw_turns_to_keep=raw_turns_to_keep,
            )
            summary_token_budget = (
                candidate.low_watermark
                - fixed_tokens
                - self.safety_margin
            )
            if summary_token_budget < self.min_summary_token_budget:
                continue

            tail_tokens = self._count_raw_turn_tokens(
                candidate=candidate,
                raw_turns=raw_turns_to_keep,
            )
            plan = VersionedCompressionPlan(
                conversation_id=candidate.plan.conversation_id,
                branch_id=candidate.plan.branch_id,
                expected_head_turn_id=self._get_expected_head_id(candidate),
                expected_pending_turn_id=(
                    candidate.plan.pending_turn.turn_id
                    if candidate.plan.pending_turn is not None
                    else None
                ),
                expected_active_summary_id=(
                    candidate.plan.summary.summary_id
                    if candidate.plan.summary is not None
                    else None
                ),
                old_summary=(
                    candidate.plan.summary.content
                    if candidate.plan.summary is not None
                    else ""
                ),
                turns_to_compress=tuple(turns_to_compress),
                raw_turns_to_keep=tuple(raw_turns_to_keep),
                summary_token_budget=summary_token_budget,
                estimated_result_upper_bound=(
                    fixed_tokens
                    + summary_token_budget
                    + self.safety_margin
                ),
            )
            feasible_plans.append((
                abs(
                    tail_tokens
                    - candidate.recent_raw_token_target
                ),
                -tail_tokens,
                plan,
            ))

        if not feasible_plans:
            return None

        feasible_plans.sort(key=lambda item: (item[0], item[1]))
        return feasible_plans[0][2]

    def _count_fixed_result_tokens(
        self,
        candidate: ContextCandidate,
        profile: Dict[str, str],
        raw_turns_to_keep: Tuple[Turn, ...],
    ) -> int:
        plan_without_summary = ContextPlan(
            conversation_id=candidate.plan.conversation_id,
            branch_id=candidate.plan.branch_id,
            summary=None,
            raw_turns=raw_turns_to_keep,
            pending_turn=candidate.plan.pending_turn,
        )
        return self.context_builder.build_from_plan(
            profile=profile,
            plan=plan_without_summary,
        ).estimated_tokens

    def _count_raw_turn_tokens(
        self,
        candidate: ContextCandidate,
        raw_turns: Tuple[Turn, ...],
    ) -> int:
        raw_only_plan = ContextPlan(
            conversation_id=candidate.plan.conversation_id,
            branch_id=candidate.plan.branch_id,
            summary=None,
            raw_turns=raw_turns,
            pending_turn=None,
        )
        return self.context_builder.build_from_plan(
            profile={},
            plan=raw_only_plan,
        ).estimated_tokens

    @staticmethod
    def _get_expected_head_id(
        candidate: ContextCandidate,
    ) -> Optional[str]:
        if candidate.plan.raw_turns:
            return candidate.plan.raw_turns[-1].turn_id
        if candidate.plan.summary is not None:
            return candidate.plan.summary.covered_until_turn_id
        return None


class _StaleCompressionPlan(Exception):
    """压缩期间分支状态已经变化。"""


class VersionedContextCompressionService:
    """执行压缩 LLM 调用并安全追加 SummaryVersion。"""

    def __init__(
        self,
        repository: ConversationRepository,
        context_planner: ContextPlanner,
        batch_planner: CompressionBatchPlanner,
        compressor: Compressor,
    ) -> None:
        self.repository = repository
        self.context_planner = context_planner
        self.batch_planner = batch_planner
        self.compressor = compressor

    async def compress_if_needed(
        self,
        conversation_id: str,
        branch_id: str,
        profile: Dict[str, str],
    ) -> VersionedCompressionOutcome:
        """同步执行至多一次追加式压缩。"""
        conversation = await self.repository.load(conversation_id)
        candidate = self.context_planner.build_candidate(
            conversation=conversation,
            profile=profile,
            branch_id=branch_id,
        )
        if not candidate.needs_compression:
            return VersionedCompressionOutcome(
                candidate=candidate,
                summary=None,
                compressed=False,
                stale=False,
                warning=None,
            )

        plan = self.batch_planner.plan(candidate, profile)
        if plan is None:
            return VersionedCompressionOutcome(
                candidate=candidate,
                summary=None,
                compressed=False,
                stale=False,
                warning=(
                    "上下文已超过质量高水位，但当前没有可安全压缩的完整轮次；"
                    "本轮将使用降级 Context。"
                ),
            )

        compression_result = await self.compressor.compress(
            CompressionRequest(
                old_summary=plan.old_summary,
                messages_to_compress=self._turns_to_messages(
                    plan.turns_to_compress
                ),
                summary_token_budget=plan.summary_token_budget,
            )
        )
        summary_content = compression_result.summary.strip()
        if not summary_content:
            raise LLMResponseError("压缩器返回了空摘要")

        new_summary = SummaryVersion(
            summary_id=str(uuid4()),
            parent_summary_id=plan.expected_active_summary_id,
            covered_until_turn_id=(
                plan.turns_to_compress[-1].turn_id
            ),
            content=summary_content,
            created_at=datetime.now(timezone.utc),
        )

        try:
            updated = await self.repository.update(
                conversation_id,
                self._build_summary_updater(plan, new_summary),
            )
        except _StaleCompressionPlan:
            current = await self.repository.load(conversation_id)
            current_candidate = self.context_planner.build_candidate(
                conversation=current,
                profile=profile,
                branch_id=branch_id,
            )
            return VersionedCompressionOutcome(
                candidate=current_candidate,
                summary=None,
                compressed=False,
                stale=True,
                warning="压缩期间剧情分支已变化，本次摘要结果已安全丢弃。",
            )

        updated_candidate = self.context_planner.build_candidate(
            conversation=updated,
            profile=profile,
            branch_id=branch_id,
        )
        return VersionedCompressionOutcome(
            candidate=updated_candidate,
            summary=new_summary,
            compressed=True,
            stale=False,
            warning=None,
        )

    @staticmethod
    def _turns_to_messages(
        turns: Tuple[Turn, ...],
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        for turn in turns:
            if turn.assistant_content is None:
                raise ValueError("压缩批次只能包含 completed Turn")
            messages.append({
                "role": "user",
                "content": turn.user_content,
            })
            messages.append({
                "role": "assistant",
                "content": turn.assistant_content,
            })
        return messages

    @staticmethod
    def _build_summary_updater(
        plan: VersionedCompressionPlan,
        new_summary: SummaryVersion,
    ):
        def update(conversation: Conversation) -> Conversation:
            branch = conversation.branches.get(plan.branch_id)
            if branch is None:
                raise _StaleCompressionPlan()
            if (
                branch.head_turn_id != plan.expected_head_turn_id
                or branch.pending_turn_id
                != plan.expected_pending_turn_id
                or branch.active_summary_id
                != plan.expected_active_summary_id
            ):
                raise _StaleCompressionPlan()

            conversation.summaries[new_summary.summary_id] = new_summary
            branch.active_summary_id = new_summary.summary_id
            return conversation

        return update
