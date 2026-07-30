"""校验浏览器只提交了目标节点对应的完整当前路径。"""

from app.exceptions.learning_errors import LearningGraphRuleError
from app.learning.contracts.commands import (
    ActivePathContext,
    ConversationAction,
)
from app.learning.domain.models import LearningConversation


class ActivePathValidator:
    """阻止缺失历史、混入兄弟节点或路径顺序错误。"""

    def validate(
        self,
        conversation: LearningConversation,
        action: ConversationAction,
        source_turn_id: str | None,
        path: ActivePathContext,
    ) -> None:
        """验证摘要覆盖点和近期原文能连续到达来源节点。"""
        if action == ConversationAction.CREATE_ROOT:
            if path.summary is not None or path.recent_turns:
                raise LearningGraphRuleError("创建根节点不能携带历史路径")
            return

        if source_turn_id is None:
            raise LearningGraphRuleError("当前路径缺少来源节点")
        if source_turn_id not in conversation.turns:
            raise LearningGraphRuleError("当前路径的来源节点不存在")

        summary = path.summary
        recent = path.recent_turns
        if summary is not None:
            covered_turn_id = summary.covered_until_turn_id
            if covered_turn_id not in conversation.turns:
                raise LearningGraphRuleError("摘要覆盖点不在当前图中")
            if not conversation.is_ancestor(
                covered_turn_id,
                source_turn_id,
            ):
                raise LearningGraphRuleError("摘要不属于当前来源路径")
        recent_ids = [turn.turn_id for turn in recent]
        if len(recent_ids) != len(set(recent_ids)):
            raise LearningGraphRuleError("当前路径包含重复 Turn")

        for turn in recent:
            graph_turn = conversation.turns.get(turn.turn_id)
            if graph_turn is None:
                raise LearningGraphRuleError("当前路径包含图外 Turn")
            if graph_turn.parent_turn_id != turn.parent_turn_id:
                raise LearningGraphRuleError("当前路径父节点与图快照不一致")

        if recent:
            if recent[-1].turn_id != source_turn_id:
                raise LearningGraphRuleError("当前路径没有结束在来源节点")
            for previous, current in zip(recent, recent[1:]):
                if current.parent_turn_id != previous.turn_id:
                    raise LearningGraphRuleError("当前路径原文不是连续祖先链")

            expected_parent = (
                summary.covered_until_turn_id
                if summary is not None
                else None
            )
            if recent[0].parent_turn_id != expected_parent:
                raise LearningGraphRuleError("当前路径缺失未摘要的祖先节点")
            return

        if summary is None:
            raise LearningGraphRuleError("非根节点操作不能提交空历史")
        if summary.covered_until_turn_id != source_turn_id:
            raise LearningGraphRuleError("摘要没有覆盖到当前来源节点")
