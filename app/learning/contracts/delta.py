"""后端返回给浏览器原子应用的会话增量。"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.learning.domain.models import (
    Citation,
    LearningBranch,
    LearningTurn,
    SummaryVersion,
)


class BranchHeadUpdate(BaseModel):
    """一个既有 Branch 的末端和摘要书签更新。"""

    model_config = ConfigDict(extra="forbid")

    branch_id: str = Field(min_length=1)
    old_head_turn_id: str | None = None
    new_head_turn_id: str = Field(min_length=1)
    new_active_summary_id: str | None = None


class ConversationDelta(BaseModel):
    """一次成功操作产生的追加记录和可移动书签。"""

    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1)
    old_revision: int = Field(ge=0)
    new_revision: int = Field(ge=1)
    added_turns: tuple[LearningTurn, ...]
    added_branches: tuple[LearningBranch, ...] = ()
    added_summaries: tuple[SummaryVersion, ...] = ()
    added_citations: tuple[Citation, ...] = ()
    branch_head_updates: tuple[BranchHeadUpdate, ...] = ()
    next_active_branch_id: str = Field(min_length=1)
    next_active_head_turn_id: str = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    usage: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_revision(self) -> "ConversationDelta":
        """一次成功操作必须只推进一个本地修订号。"""
        if self.new_revision != self.old_revision + 1:
            raise ValueError("ConversationDelta 必须将 revision 推进一位")
        if len(self.added_turns) != 1:
            raise ValueError("一次操作必须且只能新增一个完整 Turn")
        if (
            self.added_turns[0].turn_id
            != self.next_active_head_turn_id
        ):
            raise ValueError("新增 Turn 必须成为下一活动节点")
        return self
