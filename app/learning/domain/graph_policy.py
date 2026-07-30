"""学习会话图的创建规则与端口分配策略。"""

from dataclasses import dataclass

from app.exceptions.learning_errors import LearningGraphRuleError
from app.learning.domain.models import (
    ConnectionKind,
    ConversationAction,
    LearningConversation,
    NodePort,
)


@dataclass(frozen=True)
class GraphPlacement:
    """一次新节点操作经过验证后的稳定放置结果。"""

    parent_turn_id: str | None
    connection_kind: ConnectionKind
    parent_port: NodePort | None


class LearningGraphPolicy:
    """只依赖图快照执行节点连接规则，不执行任何 I/O。"""

    def plan(
        self,
        conversation: LearningConversation,
        action: ConversationAction,
        source_turn_id: str | None,
        branch_id: str | None,
        preferred_port: NodePort | None = None,
    ) -> GraphPlacement:
        """验证操作并返回服务端最终采用的连接位置。"""
        if action == ConversationAction.CREATE_ROOT:
            return self._plan_root(conversation)

        if source_turn_id is None:
            raise LearningGraphRuleError("非根节点操作必须指定来源节点")
        if source_turn_id not in conversation.turns:
            raise LearningGraphRuleError("来源节点不存在")

        if action == ConversationAction.APPEND_TURN:
            return self._plan_continue(
                conversation,
                source_turn_id,
                branch_id,
            )
        if action == ConversationAction.FORK_FROM_TURN:
            return self._plan_fork(
                conversation,
                source_turn_id,
                preferred_port,
            )
        raise LearningGraphRuleError(f"不支持的图操作：{action}")

    @staticmethod
    def _plan_root(
        conversation: LearningConversation,
    ) -> GraphPlacement:
        if conversation.turns or conversation.root_turn_id is not None:
            raise LearningGraphRuleError("非空会话不能再次创建根节点")
        return GraphPlacement(
            parent_turn_id=None,
            connection_kind=ConnectionKind.ROOT,
            parent_port=None,
        )

    @staticmethod
    def _plan_continue(
        conversation: LearningConversation,
        source_turn_id: str,
        branch_id: str | None,
    ) -> GraphPlacement:
        if branch_id is None or branch_id not in conversation.branches:
            raise LearningGraphRuleError("普通续写必须指定有效分支")

        branch = conversation.branches[branch_id]
        if branch.head_turn_id != source_turn_id:
            raise LearningGraphRuleError("普通续写只能发生在分支末端")

        source = conversation.turns[source_turn_id]
        target_port = (
            NodePort.BOTTOM
            if source.connection_kind == ConnectionKind.ROOT
            else source.parent_port
        )
        assert target_port is not None
        LearningGraphPolicy._ensure_port_available(
            conversation,
            source_turn_id,
            target_port,
        )
        return GraphPlacement(
            parent_turn_id=source_turn_id,
            connection_kind=ConnectionKind.CONTINUE,
            parent_port=target_port,
        )

    @staticmethod
    def _plan_fork(
        conversation: LearningConversation,
        source_turn_id: str,
        preferred_port: NodePort | None,
    ) -> GraphPlacement:
        source = conversation.turns[source_turn_id]
        if source.connection_kind == ConnectionKind.ROOT:
            raise LearningGraphRuleError("根节点不允许创建分支")

        assert source.parent_port is not None
        available_ports = [
            port
            for port in source.parent_port.perpendicular
            if LearningGraphPolicy._is_port_available(
                conversation,
                source_turn_id,
                port,
            )
        ]
        if not available_ports:
            raise LearningGraphRuleError("当前节点没有可用的转弯端口")

        if preferred_port is not None:
            if preferred_port not in available_ports:
                raise LearningGraphRuleError("前端建议的分支端口不可用")
            target_port = preferred_port
        else:
            target_port = available_ports[0]

        return GraphPlacement(
            parent_turn_id=source_turn_id,
            connection_kind=ConnectionKind.FORK,
            parent_port=target_port,
        )

    @staticmethod
    def _is_port_available(
        conversation: LearningConversation,
        source_turn_id: str,
        port: NodePort,
    ) -> bool:
        return all(
            turn.parent_turn_id != source_turn_id
            or turn.parent_port != port
            for turn in conversation.turns.values()
        )

    @classmethod
    def _ensure_port_available(
        cls,
        conversation: LearningConversation,
        source_turn_id: str,
        port: NodePort,
    ) -> None:
        if not cls._is_port_available(
            conversation,
            source_turn_id,
            port,
        ):
            raise LearningGraphRuleError("目标端口已被其他节点占用")
