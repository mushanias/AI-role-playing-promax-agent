"""浏览器提交给无状态后端的学习会话命令。"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.learning.domain.models import (
    ConnectionKind,
    ConversationAction,
    NodePort,
    SummaryVersion,
)


class RetrievalMode(str, Enum):
    """用户为当前问答选择的资料来源范围。"""

    AUTO = "auto"
    KNOWLEDGE_BASE_ONLY = "knowledge_base_only"
    WEB_ONLY = "web_only"
    KNOWLEDGE_BASE_AND_WEB = "knowledge_base_and_web"


class StableContext(BaseModel):
    """一个学习目标创建后不可变的用户背景和目标。"""

    model_config = ConfigDict(extra="forbid")

    background: str = Field(min_length=1)
    learning_goal: str = Field(min_length=1)
    target_level: str = Field(min_length=1)
    time_budget: Optional[str] = None
    constraints: tuple[str, ...] = ()


class PromptSnapshot(BaseModel):
    """创建学习目标时从模板复制出的不可变 Prompt。"""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: Literal["builtin", "custom"]
    version: int = Field(ge=1)
    content: str = Field(min_length=1)


class RuntimeModelConfig(BaseModel):
    """不包含 API Key 的当前模型运行配置。"""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


class CompactTurn(BaseModel):
    """用于验证图结构的最小节点索引。"""

    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(min_length=1)
    parent_turn_id: Optional[str] = None
    connection_kind: ConnectionKind
    parent_port: Optional[NodePort] = None


class CompactBranch(BaseModel):
    """用于验证分支末端的最小分支索引。"""

    model_config = ConfigDict(extra="forbid")

    branch_id: str = Field(min_length=1)
    parent_branch_id: Optional[str] = None
    forked_from_turn_id: Optional[str] = None
    head_turn_id: Optional[str] = None
    active_summary_id: Optional[str] = None


class CompactGraph(BaseModel):
    """浏览器发送的无正文图快照。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    conversation_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    main_branch_id: str = Field(min_length=1)
    root_turn_id: Optional[str] = None
    turns: tuple[CompactTurn, ...] = ()
    branches: tuple[CompactBranch, ...]


class PathTurn(BaseModel):
    """当前路径中尚未被摘要覆盖的完整问答。"""

    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(min_length=1)
    parent_turn_id: Optional[str] = None
    user_content: str = Field(min_length=1)
    assistant_content: str = Field(min_length=1)


class ActivePathContext(BaseModel):
    """只包含当前路径的摘要和近期原文。"""

    model_config = ConfigDict(extra="forbid")

    summary: Optional[SummaryVersion] = None
    recent_turns: tuple[PathTurn, ...] = ()


class ConversationCommand(BaseModel):
    """一次非流式学习对话的完整输入契约。"""

    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    action: ConversationAction
    goal_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    new_turn_id: str = Field(min_length=1)
    source_turn_id: Optional[str] = None
    active_branch_id: Optional[str] = None
    new_branch_id: Optional[str] = None
    preferred_port: Optional[NodePort] = None
    user_text: str = Field(min_length=1)
    retrieval_mode: RetrievalMode = RetrievalMode.AUTO
    compact_graph: CompactGraph
    active_path_context: ActivePathContext
    stable_context: StableContext
    prompt_snapshot: PromptSnapshot
    runtime_model: RuntimeModelConfig

    @model_validator(mode="after")
    def validate_action_fields(self) -> "ConversationCommand":
        """保证不同图操作只携带自己需要的定位字段。"""
        if self.conversation_id != self.compact_graph.conversation_id:
            raise ValueError("命令与图快照的 conversation_id 不一致")
        if self.expected_revision != self.compact_graph.revision:
            raise ValueError("expected_revision 与图快照 revision 不一致")

        if self.action == ConversationAction.CREATE_ROOT:
            if any(
                value is not None
                for value in (
                    self.source_turn_id,
                    self.active_branch_id,
                    self.new_branch_id,
                    self.preferred_port,
                )
            ):
                raise ValueError("创建根节点不能包含分支定位字段")
            return self

        if self.source_turn_id is None:
            raise ValueError("非根操作必须指定 source_turn_id")

        if self.active_branch_id is None:
            raise ValueError("非根操作必须指定 active_branch_id")

        if self.action == ConversationAction.APPEND_TURN:
            if self.new_branch_id is not None or self.preferred_port is not None:
                raise ValueError("普通续写不能包含新分支字段")
            return self

        if self.new_branch_id is None:
            raise ValueError("创建分支必须指定 new_branch_id")
        if self.new_branch_id == self.active_branch_id:
            raise ValueError("新分支 ID 不能等于当前分支 ID")
        return self
