from collections.abc import Sequence
from dataclasses import dataclass
from typing import Dict, List, Mapping, Protocol

from app.conversations.memory.context_plan import ContextPlan


class MessageTokenCounter(Protocol):
    """ContextBuilder 所需的最小 Token 计算接口。"""

    def count_messages(
        self,
        messages: Sequence[Mapping[str, str]],
    ) -> int:
        ...


@dataclass(frozen=True)
class PlannedContextBuildResult:
    """根据新 ContextPlan 生成的实际消息和 Token 估算。"""

    messages: tuple[Dict[str, str], ...]
    estimated_tokens: int


class ContextBuilder:
    """根据 ContextPlan 组装本轮候选消息。"""

    def __init__(
        self,
        token_counter: MessageTokenCounter,
    ) -> None:
        self.token_counter = token_counter

    def build_from_plan(
        self,
        plan: ContextPlan,
    ) -> PlannedContextBuildResult:
        """把语义化 Context 计划转换为最终 LLM messages。"""
        summary_content = (
            plan.summary.content if plan.summary is not None else ""
        )
        system_content = self._build_system_content(summary_content)
        messages: List[Dict[str, str]] = [
            dict(message) for message in plan.prefix_messages
        ]

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

    @staticmethod
    def _build_system_content(summary: str) -> str:
        """把活动摘要组装为 system 内容。"""
        if not summary:
            return ""
        return f"【历史摘要】\n{summary}"
