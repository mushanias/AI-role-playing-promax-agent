"""分支 Context 规划：解析当前历史链并执行质量水位判断。"""

from typing import Dict, List, Optional, Tuple

from app.exceptions import BranchNotFoundError
from app.conversations.conversation import Branch, Conversation, Turn
from app.conversations.memory.context_builder import ContextBuilder
from app.conversations.memory.context_plan import ContextCandidate, ContextPlan


class ContextPlanner:
    """根据内存会话模型生成一轮候选 Context。"""

    def __init__(
        self,
        context_builder: ContextBuilder,
        high_watermark: int,
        low_watermark: int,
        recent_raw_token_target: int,
    ) -> None:
        if high_watermark <= 0:
            raise ValueError("Context 高水位必须大于 0")
        if low_watermark <= 0:
            raise ValueError("Context 低水位必须大于 0")
        if low_watermark >= high_watermark:
            raise ValueError("Context 低水位必须小于高水位")
        if recent_raw_token_target <= 0:
            raise ValueError("近期原文目标必须大于 0")
        if recent_raw_token_target >= low_watermark:
            raise ValueError("近期原文目标必须小于低水位")

        self.context_builder = context_builder
        self.high_watermark = high_watermark
        self.low_watermark = low_watermark
        self.recent_raw_token_target = recent_raw_token_target

    def build_candidate(
        self,
        conversation: Conversation,
        branch_id: Optional[str] = None,
        prefix_messages: Tuple[Dict[str, str], ...] = (),
    ) -> ContextCandidate:
        """选择指定分支 Context，并用实际 messages 判断水位。"""
        selected_branch_id = branch_id or conversation.active_branch_id
        branch = conversation.branches.get(selected_branch_id)
        if branch is None:
            raise BranchNotFoundError(
                f"会话分支不存在：{selected_branch_id}"
            )

        completed_path = self._collect_completed_path(
            conversation,
            branch,
        )
        summary = (
            conversation.summaries[branch.active_summary_id]
            if branch.active_summary_id is not None
            else None
        )
        raw_turns = self._select_uncovered_turns(
            completed_path,
            covered_until_turn_id=(
                summary.covered_until_turn_id
                if summary is not None
                else None
            ),
        )
        pending_turn = (
            conversation.turns[branch.pending_turn_id]
            if branch.pending_turn_id is not None
            else None
        )
        plan = ContextPlan(
            conversation_id=conversation.conversation_id,
            branch_id=selected_branch_id,
            summary=summary,
            raw_turns=tuple(raw_turns),
            pending_turn=pending_turn,
            prefix_messages=prefix_messages,
        )
        built = self.context_builder.build_from_plan(plan)

        return ContextCandidate(
            plan=plan,
            messages=built.messages,
            estimated_tokens=built.estimated_tokens,
            high_watermark=self.high_watermark,
            low_watermark=self.low_watermark,
            recent_raw_token_target=self.recent_raw_token_target,
            needs_compression=(
                built.estimated_tokens > self.high_watermark
            ),
        )

    @staticmethod
    def _collect_completed_path(
        conversation: Conversation,
        branch: Branch,
    ) -> List[Turn]:
        """从 HEAD 回溯并返回按时间正序排列的完成轮次。"""
        reversed_path: List[Turn] = []
        current_turn_id = branch.head_turn_id

        while current_turn_id is not None:
            turn = conversation.turns[current_turn_id]
            reversed_path.append(turn)
            current_turn_id = turn.parent_turn_id

        reversed_path.reverse()
        return reversed_path

    @staticmethod
    def _select_uncovered_turns(
        completed_path: List[Turn],
        covered_until_turn_id: Optional[str],
    ) -> List[Turn]:
        """返回活动摘要覆盖终点之后的原始完成轮次。"""
        if covered_until_turn_id is None:
            return completed_path

        for index, turn in enumerate(completed_path):
            if turn.turn_id == covered_until_turn_id:
                return completed_path[index + 1:]

        raise ValueError("活动摘要覆盖终点不在当前 Branch 历史链上")
