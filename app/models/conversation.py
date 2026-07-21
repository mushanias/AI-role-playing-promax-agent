"""会话历史领域模型：描述原始轮次、剧情分支与摘要版本。"""

from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TurnStatus(str, Enum):
    """原始对话轮次的生命周期状态。"""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Turn(BaseModel):
    """一次用户输入及其对应助手回复组成的原始轮次。"""

    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(min_length=1)
    parent_turn_id: Optional[str] = None
    user_content: str
    assistant_content: Optional[str] = None
    status: TurnStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    failure_message: Optional[str] = None

    @model_validator(mode="after")
    def validate_state(self) -> "Turn":
        """保证轮次内容与生命周期状态一致。"""
        if self.parent_turn_id == self.turn_id:
            raise ValueError("Turn 不能把自己作为父轮次")

        if self.status == TurnStatus.PENDING:
            if self.assistant_content is not None:
                raise ValueError("pending Turn 不能包含助手最终回复")
            if self.completed_at is not None:
                raise ValueError("pending Turn 不能包含完成时间")
            if self.failure_message is not None:
                raise ValueError("pending Turn 不能包含失败信息")

        elif self.status == TurnStatus.COMPLETED:
            if self.assistant_content is None:
                raise ValueError("completed Turn 必须包含助手回复")
            if self.completed_at is None:
                raise ValueError("completed Turn 必须包含完成时间")
            if self.failure_message is not None:
                raise ValueError("completed Turn 不能包含失败信息")

        elif self.status == TurnStatus.FAILED:
            if not self.failure_message:
                raise ValueError("failed Turn 必须包含失败信息")
            if self.completed_at is not None:
                raise ValueError("failed Turn 不能包含完成时间")

        return self


class SummaryVersion(BaseModel):
    """一份追加保存、不可覆盖的历史摘要版本。"""

    model_config = ConfigDict(extra="forbid")

    summary_id: str = Field(min_length=1)
    parent_summary_id: Optional[str] = None
    covered_until_turn_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_parent(self) -> "SummaryVersion":
        """阻止摘要直接引用自身。"""
        if self.parent_summary_id == self.summary_id:
            raise ValueError("Summary 不能把自己作为父摘要")
        return self


class Branch(BaseModel):
    """一条剧情线的当前原文位置与活动摘要书签。"""

    model_config = ConfigDict(extra="forbid")

    branch_id: str = Field(min_length=1)
    parent_branch_id: Optional[str] = None
    forked_from_turn_id: Optional[str] = None
    head_turn_id: Optional[str] = None
    pending_turn_id: Optional[str] = None
    active_summary_id: Optional[str] = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_parent(self) -> "Branch":
        """阻止分支直接引用自身。"""
        if self.parent_branch_id == self.branch_id:
            raise ValueError("Branch 不能把自己作为父分支")
        return self


class Conversation(BaseModel):
    """单个会话 JSON 文件对应的聚合根。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    conversation_id: str = Field(min_length=1)
    active_branch_id: str = Field(min_length=1)
    turns: Dict[str, Turn] = Field(default_factory=dict)
    branches: Dict[str, Branch]
    summaries: Dict[str, SummaryVersion] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "Conversation":
        """校验所有跨记录指针、状态与祖先链关系。"""
        self._validate_index_keys()
        self._validate_turn_graph()
        self._validate_summary_graph()
        self._validate_branch_graph()
        self._validate_branch_references()
        return self

    def _validate_index_keys(self) -> None:
        for key, turn in self.turns.items():
            if key != turn.turn_id:
                raise ValueError("turns 的索引键必须等于 Turn.turn_id")

        for key, branch in self.branches.items():
            if key != branch.branch_id:
                raise ValueError("branches 的索引键必须等于 Branch.branch_id")

        for key, summary in self.summaries.items():
            if key != summary.summary_id:
                raise ValueError(
                    "summaries 的索引键必须等于 Summary.summary_id"
                )

    def _validate_turn_graph(self) -> None:
        for turn in self.turns.values():
            if (
                turn.parent_turn_id is not None
                and turn.parent_turn_id not in self.turns
            ):
                raise ValueError(
                    f"Turn {turn.turn_id} 指向不存在的父轮次"
                )

        self._reject_cycles(
            node_ids=set(self.turns),
            get_parent=lambda node_id: self.turns[node_id].parent_turn_id,
            graph_name="Turn",
        )

    def _validate_summary_graph(self) -> None:
        for summary in self.summaries.values():
            if summary.covered_until_turn_id not in self.turns:
                raise ValueError(
                    f"Summary {summary.summary_id} 的覆盖终点不存在"
                )

            covered_turn = self.turns[summary.covered_until_turn_id]
            if covered_turn.status != TurnStatus.COMPLETED:
                raise ValueError("Summary 只能覆盖 completed Turn")

            if (
                summary.parent_summary_id is not None
                and summary.parent_summary_id not in self.summaries
            ):
                raise ValueError(
                    f"Summary {summary.summary_id} 指向不存在的父摘要"
                )

        self._reject_cycles(
            node_ids=set(self.summaries),
            get_parent=lambda node_id: self.summaries[
                node_id
            ].parent_summary_id,
            graph_name="Summary",
        )

        for summary in self.summaries.values():
            if summary.parent_summary_id is None:
                continue

            parent = self.summaries[summary.parent_summary_id]
            if parent.covered_until_turn_id == summary.covered_until_turn_id:
                raise ValueError("子摘要必须比父摘要覆盖更多原文")

            if not self._is_turn_ancestor(
                ancestor_turn_id=parent.covered_until_turn_id,
                descendant_turn_id=summary.covered_until_turn_id,
            ):
                raise ValueError("父摘要的覆盖终点不在子摘要历史链上")

    def _validate_branch_graph(self) -> None:
        if self.active_branch_id not in self.branches:
            raise ValueError("active_branch_id 指向不存在的 Branch")

        for branch in self.branches.values():
            if (
                branch.parent_branch_id is not None
                and branch.parent_branch_id not in self.branches
            ):
                raise ValueError(
                    f"Branch {branch.branch_id} 指向不存在的父分支"
                )

            if (
                branch.forked_from_turn_id is not None
                and branch.forked_from_turn_id not in self.turns
            ):
                raise ValueError(
                    f"Branch {branch.branch_id} 的分叉轮次不存在"
                )

        self._reject_cycles(
            node_ids=set(self.branches),
            get_parent=lambda node_id: self.branches[
                node_id
            ].parent_branch_id,
            graph_name="Branch",
        )

    def _validate_branch_references(self) -> None:
        referenced_pending_turns: Set[str] = set()

        for branch in self.branches.values():
            if branch.head_turn_id is not None:
                if branch.head_turn_id not in self.turns:
                    raise ValueError(
                        f"Branch {branch.branch_id} 的 HEAD 不存在"
                    )
                if (
                    self.turns[branch.head_turn_id].status
                    != TurnStatus.COMPLETED
                ):
                    raise ValueError("Branch HEAD 必须指向 completed Turn")

            if branch.pending_turn_id is not None:
                if branch.pending_turn_id not in self.turns:
                    raise ValueError(
                        f"Branch {branch.branch_id} 的 pending Turn 不存在"
                    )

                pending_turn = self.turns[branch.pending_turn_id]
                if pending_turn.status != TurnStatus.PENDING:
                    raise ValueError(
                        "Branch.pending_turn_id 必须指向 pending Turn"
                    )
                if pending_turn.parent_turn_id != branch.head_turn_id:
                    raise ValueError(
                        "pending Turn 的父轮次必须等于当前 Branch HEAD"
                    )
                if branch.pending_turn_id in referenced_pending_turns:
                    raise ValueError("同一个 pending Turn 不能属于多个 Branch")
                referenced_pending_turns.add(branch.pending_turn_id)

            if branch.active_summary_id is not None:
                if branch.active_summary_id not in self.summaries:
                    raise ValueError(
                        f"Branch {branch.branch_id} 的活动摘要不存在"
                    )
                if branch.head_turn_id is None:
                    raise ValueError("空 Branch 不能引用活动摘要")

                summary = self.summaries[branch.active_summary_id]
                if not self._is_turn_ancestor(
                    ancestor_turn_id=summary.covered_until_turn_id,
                    descendant_turn_id=branch.head_turn_id,
                ):
                    raise ValueError(
                        "活动摘要的覆盖终点不在当前 Branch 历史链上"
                    )

            if branch.parent_branch_id is None:
                if branch.forked_from_turn_id is not None:
                    raise ValueError("根 Branch 不能包含分叉轮次")
                continue

            parent_branch = self.branches[branch.parent_branch_id]

            if branch.forked_from_turn_id is None:
                if branch.head_turn_id is not None:
                    raise ValueError("从根位置分叉的 Branch 不能直接拥有 HEAD")
                continue

            forked_turn = self.turns[branch.forked_from_turn_id]
            if forked_turn.status != TurnStatus.COMPLETED:
                raise ValueError("Branch 分叉点必须是 completed Turn")

            if parent_branch.head_turn_id is None or not self._is_turn_ancestor(
                ancestor_turn_id=branch.forked_from_turn_id,
                descendant_turn_id=parent_branch.head_turn_id,
            ):
                raise ValueError("Branch 分叉点不在父分支历史链上")

            if branch.head_turn_id is None or not self._is_turn_ancestor(
                ancestor_turn_id=branch.forked_from_turn_id,
                descendant_turn_id=branch.head_turn_id,
            ):
                raise ValueError("Branch HEAD 不在其分叉点之后的历史链上")

    def _is_turn_ancestor(
        self,
        ancestor_turn_id: str,
        descendant_turn_id: str,
    ) -> bool:
        current_turn_id: Optional[str] = descendant_turn_id

        while current_turn_id is not None:
            if current_turn_id == ancestor_turn_id:
                return True
            current_turn_id = self.turns[current_turn_id].parent_turn_id

        return False

    @staticmethod
    def _reject_cycles(
        node_ids: Set[str],
        get_parent: Callable[[str], Optional[str]],
        graph_name: str,
    ) -> None:
        """校验每个单父节点图中不存在循环引用。"""
        fully_checked: Set[str] = set()

        for start_node_id in node_ids:
            if start_node_id in fully_checked:
                continue

            current_node_id: Optional[str] = start_node_id
            current_path: Set[str] = set()

            while current_node_id is not None:
                if current_node_id in current_path:
                    raise ValueError(f"{graph_name} 历史链中存在循环引用")
                if current_node_id in fully_checked:
                    break

                current_path.add(current_node_id)
                current_node_id = get_parent(current_node_id)

            fully_checked.update(current_path)
