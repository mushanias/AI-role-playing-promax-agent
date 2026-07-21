from dataclasses import dataclass
from collections.abc import Sequence
from typing import Dict, List, Mapping, Protocol

from app.models.context_state import ContextState
from app.models.context_plan import ContextPlan


class MessageTokenCounter(Protocol):
    """ContextBuilder 所需的最小 Token 计算接口。"""

    def count_messages(
        self,
        messages: Sequence[Mapping[str, str]],
    ) -> int:
        ...


@dataclass
class ContextBuildResult:
    """一次上下文组装的结果。"""

    messages: List[Dict[str, str]]
    recent_messages: List[Dict[str, str]]
    estimated_tokens: int
    needs_compression: bool


@dataclass(frozen=True)
class PlannedContextBuildResult:
    """根据新 ContextPlan 生成的实际消息和 Token 估算。"""

    messages: tuple[Dict[str, str], ...]
    estimated_tokens: int


class ContextBuilder:
    """根据历史、设定和状态组装本轮候选上下文。"""

    def __init__(
        self,
        token_counter: MessageTokenCounter,
        input_token_budget: int,
    ) -> None:
        if input_token_budget <= 0:
            raise ValueError("输入 token 预算必须大于 0")

        self.token_counter = token_counter
        self.input_token_budget = input_token_budget

    def build(
        self,
        profile: Dict[str, str],
        history: List[Dict[str, str]],
        state: ContextState,
    ) -> ContextBuildResult:
        recent_messages = self._get_recent_messages(history, state)
        system_content = self._build_system_content(profile, state)

        messages = []

        if system_content:
            messages.append({
                "role": "system",
                "content": system_content,
            })

        messages.extend(
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in recent_messages
        )

        estimated_tokens = self.token_counter.count_messages(messages)

        return ContextBuildResult(
            messages=messages,
            estimated_tokens=estimated_tokens,
            needs_compression=(
                estimated_tokens > self.input_token_budget
            ),
            recent_messages=recent_messages,
        )

    def build_from_plan(
        self,
        profile: Dict[str, str],
        plan: ContextPlan,
    ) -> PlannedContextBuildResult:
        """把语义化 Context 计划转换为最终 LLM messages。"""
        summary_content = (
            plan.summary.content if plan.summary is not None else ""
        )
        system_content = self._join_system_content(
            profile=profile,
            summary=summary_content,
        )
        messages: List[Dict[str, str]] = []

        if system_content:
            messages.append({
                "role": "system",
                "content": system_content,
            })

        for turn in plan.raw_turns:
            if turn.assistant_content is None:
                raise ValueError("Context 原文只能包含已完成轮次")
            messages.append({
                "role": "user",
                "content": turn.user_content,
            })
            messages.append({
                "role": "assistant",
                "content": turn.assistant_content,
            })

        if plan.pending_turn is not None:
            messages.append({
                "role": "user",
                "content": plan.pending_turn.user_content,
            })

        frozen_messages = tuple(messages)
        return PlannedContextBuildResult(
            messages=frozen_messages,
            estimated_tokens=self.token_counter.count_messages(
                frozen_messages
            ),
        )

    def _get_recent_messages(
        self,
        history: List[Dict[str, str]],
        state: ContextState,
    ) -> List[Dict[str, str]]:
        """返回尚未被摘要覆盖的原始消息。"""
        pointer = state.compressed_until_message_id

        if pointer is None:
            return history

        for index, message in enumerate(history):
            if message["message_id"] == pointer:
                return history[index + 1:]

        raise ValueError(
            "ContextState 的压缩边界在原始历史中不存在"
        )

    def _build_system_content(
        self,
        profile: Dict[str, str],
        state: ContextState,
    ) -> str:
        """组装角色设定与历史摘要。"""
        return self._join_system_content(
            profile=profile,
            summary=state.summary,
        )

    @staticmethod
    def _join_system_content(
        profile: Dict[str, str],
        summary: str,
    ) -> str:
        """按固定顺序组装全局设定与活动摘要。"""
        parts = []

        for key, value in profile.items():
            parts.append(f"【{key}】\n{value}")

        if summary:
            parts.append(f"【历史摘要】\n{summary}")

        return "\n\n".join(parts)
