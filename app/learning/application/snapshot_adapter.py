"""把浏览器的紧凑图契约还原为可验证领域快照。"""

from datetime import UTC, datetime

from pydantic import ValidationError

from app.exceptions.learning_errors import LearningGraphRuleError
from app.learning.contracts.commands import CompactGraph
from app.learning.domain.models import (
    LearningBranch,
    LearningConversation,
    LearningTurn,
)


class CompactGraphAdapter:
    """隔离 HTTP 紧凑格式与完整领域聚合之间的差异。"""

    def to_conversation(
        self,
        graph: CompactGraph,
    ) -> LearningConversation:
        """使用无业务意义的占位正文还原拓扑并触发完整校验。"""
        turns = self._unique_index(
            graph.turns,
            "turn_id",
            "紧凑图中存在重复 Turn ID",
        )
        branches = self._unique_index(
            graph.branches,
            "branch_id",
            "紧凑图中存在重复 Branch ID",
        )
        placeholder_time = datetime(1970, 1, 1, tzinfo=UTC)

        try:
            return LearningConversation(
                conversation_id=graph.conversation_id,
                revision=graph.revision,
                main_branch_id=graph.main_branch_id,
                root_turn_id=graph.root_turn_id,
                turns={
                    turn_id: LearningTurn(
                        turn_id=turn.turn_id,
                        parent_turn_id=turn.parent_turn_id,
                        connection_kind=turn.connection_kind,
                        parent_port=turn.parent_port,
                        user_content="[紧凑图未传输正文]",
                        assistant_content="[紧凑图未传输正文]",
                        provider="snapshot",
                        model="snapshot",
                        created_at=placeholder_time,
                    )
                    for turn_id, turn in turns.items()
                },
                branches={
                    branch_id: LearningBranch(
                        branch_id=branch.branch_id,
                        parent_branch_id=branch.parent_branch_id,
                        forked_from_turn_id=branch.forked_from_turn_id,
                        head_turn_id=branch.head_turn_id,
                        active_summary_id=None,
                        created_at=placeholder_time,
                    )
                    for branch_id, branch in branches.items()
                },
            )
        except (ValidationError, ValueError) as error:
            raise LearningGraphRuleError(
                f"紧凑图结构不合法：{error}"
            ) from None

    @staticmethod
    def _unique_index(
        records: tuple,
        id_field: str,
        error_message: str,
    ) -> dict:
        index = {
            getattr(record, id_field): record
            for record in records
        }
        if len(index) != len(records):
            raise LearningGraphRuleError(error_message)
        return index
