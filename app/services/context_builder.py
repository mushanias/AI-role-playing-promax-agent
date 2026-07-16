from dataclasses import dataclass
from typing import Dict, List

from app.models.context_state import ContextState
from app.services.token_counter import TokenCounter


@dataclass
class ContextBuildResult:
    """一次上下文组装的结果。"""

    messages: List[Dict[str, str]]
    recent_messages: List[Dict[str, str]]
    estimated_tokens: int
    needs_compression: bool


class ContextBuilder:
    """根据历史、设定和状态组装本轮候选上下文。"""

    def __init__(
        self,
        token_counter: TokenCounter,
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
        parts = []

        for key, value in profile.items():
            parts.append(f"【{key}】\n{value}")

        if state.summary:
            parts.append(f"【历史摘要】\n{state.summary}")

        return "\n\n".join(parts)