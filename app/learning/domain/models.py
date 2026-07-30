"""学习会话图的稳定领域模型。"""

from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodePort(str, Enum):
    """一个节点可以连接的四个物理方向。"""

    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"

    @property
    def opposite(self) -> "NodePort":
        """返回当前方向的相反方向。"""
        return {
            NodePort.TOP: NodePort.BOTTOM,
            NodePort.RIGHT: NodePort.LEFT,
            NodePort.BOTTOM: NodePort.TOP,
            NodePort.LEFT: NodePort.RIGHT,
        }[self]

    @property
    def perpendicular(self) -> tuple["NodePort", "NodePort"]:
        """按稳定顺序返回两个垂直方向。"""
        return {
            NodePort.TOP: (NodePort.LEFT, NodePort.RIGHT),
            NodePort.RIGHT: (NodePort.TOP, NodePort.BOTTOM),
            NodePort.BOTTOM: (NodePort.RIGHT, NodePort.LEFT),
            NodePort.LEFT: (NodePort.BOTTOM, NodePort.TOP),
        }[self]


class ConnectionKind(str, Enum):
    """节点相对父节点的连接语义。"""

    ROOT = "root"
    CONTINUE = "continue"
    FORK = "fork"


class ConversationAction(str, Enum):
    """一次命令允许执行的图操作。"""

    CREATE_ROOT = "create_root"
    APPEND_TURN = "append_turn"
    FORK_FROM_TURN = "fork_from_turn"


class CitationSource(str, Enum):
    """引用资料的来源类型。"""

    KNOWLEDGE_BASE = "knowledge_base"
    WEB = "web"


class LearningTurn(BaseModel):
    """一次已经完成、可以进入正式会话图的完整问答。"""

    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(min_length=1)
    parent_turn_id: Optional[str] = None
    connection_kind: ConnectionKind
    parent_port: Optional[NodePort] = None
    user_content: str = Field(min_length=1)
    assistant_content: str = Field(min_length=1)
    citation_ids: tuple[str, ...] = ()
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_connection(self) -> "LearningTurn":
        """保证根节点和普通节点使用一致的连接字段。"""
        if self.parent_turn_id == self.turn_id:
            raise ValueError("Turn 不能把自己作为父节点")

        if self.connection_kind == ConnectionKind.ROOT:
            if self.parent_turn_id is not None or self.parent_port is not None:
                raise ValueError("根 Turn 不能包含父节点或父端口")
            return self

        if self.parent_turn_id is None or self.parent_port is None:
            raise ValueError("非根 Turn 必须包含父节点和父端口")
        return self


class LearningBranch(BaseModel):
    """一条学习路径的末端书签，不复制公共祖先节点。"""

    model_config = ConfigDict(extra="forbid")

    branch_id: str = Field(min_length=1)
    parent_branch_id: Optional[str] = None
    forked_from_turn_id: Optional[str] = None
    head_turn_id: Optional[str] = None
    active_summary_id: Optional[str] = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_parent(self) -> "LearningBranch":
        """阻止分支直接引用自己。"""
        if self.parent_branch_id == self.branch_id:
            raise ValueError("Branch 不能把自己作为父分支")
        return self


class SummaryVersion(BaseModel):
    """一份针对特定路径追加保存的学习状态摘要。"""

    model_config = ConfigDict(extra="forbid")

    summary_id: str = Field(min_length=1)
    parent_summary_id: Optional[str] = None
    covered_until_turn_id: str = Field(min_length=1)
    path_fingerprint: str = Field(min_length=1)
    content: str = Field(min_length=1)
    learning_plan_state: Optional[str] = None
    completed_items: tuple[str, ...] = ()
    current_item: Optional[str] = None
    user_decisions: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def validate_parent(self) -> "SummaryVersion":
        """阻止摘要直接引用自己。"""
        if self.parent_summary_id == self.summary_id:
            raise ValueError("Summary 不能把自己作为父摘要")
        return self


class Citation(BaseModel):
    """一条可以由前端统一展示的资料来源。"""

    model_config = ConfigDict(extra="forbid")

    citation_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    source: CitationSource
    title: str = Field(min_length=1)
    url: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime
    knowledge_base_version: Optional[str] = None
    reference_id: Optional[str] = None


class LearningConversation(BaseModel):
    """浏览器持久化的学习会话图快照。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    conversation_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    main_branch_id: str = Field(min_length=1)
    root_turn_id: Optional[str] = None
    turns: Dict[str, LearningTurn] = Field(default_factory=dict)
    branches: Dict[str, LearningBranch]
    summaries: Dict[str, SummaryVersion] = Field(default_factory=dict)
    citations: Dict[str, Citation] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "LearningConversation":
        """校验图索引、连接方向和所有跨记录引用。"""
        self._validate_index_keys()
        self._validate_turns()
        self._validate_summaries()
        self._validate_branches()
        self._validate_citations()
        return self

    def _validate_index_keys(self) -> None:
        indexes = (
            ("turns", self.turns, "turn_id"),
            ("branches", self.branches, "branch_id"),
            ("summaries", self.summaries, "summary_id"),
            ("citations", self.citations, "citation_id"),
        )
        for index_name, index, id_field in indexes:
            for key, value in index.items():
                if key != getattr(value, id_field):
                    raise ValueError(f"{index_name} 的索引键与记录 ID 不一致")

    def _validate_turns(self) -> None:
        if not self.turns:
            if self.root_turn_id is not None:
                raise ValueError("空会话不能包含 root_turn_id")
            return

        if self.root_turn_id is None or self.root_turn_id not in self.turns:
            raise ValueError("非空会话必须包含有效根 Turn")

        roots = [
            turn
            for turn in self.turns.values()
            if turn.connection_kind == ConnectionKind.ROOT
        ]
        if len(roots) != 1 or roots[0].turn_id != self.root_turn_id:
            raise ValueError("会话必须且只能包含一个指定的根 Turn")

        children_by_parent: dict[str, list[LearningTurn]] = {}
        for turn in self.turns.values():
            if turn.parent_turn_id is None:
                continue
            if turn.parent_turn_id not in self.turns:
                raise ValueError(
                    f"Turn {turn.turn_id} 指向不存在的父节点"
                )
            children_by_parent.setdefault(turn.parent_turn_id, []).append(turn)

        self._reject_cycles(
            node_ids=set(self.turns),
            get_parent=lambda turn_id: self.turns[turn_id].parent_turn_id,
            graph_name="Turn",
        )

        for parent_id, children in children_by_parent.items():
            parent = self.turns[parent_id]
            occupied_ports = [child.parent_port for child in children]
            if len(set(occupied_ports)) != len(occupied_ports):
                raise ValueError("同一个节点的物理端口不能连接多个子节点")

            if parent.connection_kind == ConnectionKind.ROOT:
                if len(children) > 1:
                    raise ValueError("根节点最多只能拥有一个普通后继")
                child = children[0]
                if (
                    child.connection_kind != ConnectionKind.CONTINUE
                    or child.parent_port != NodePort.BOTTOM
                ):
                    raise ValueError("根节点只能向下创建普通后继")
                continue

            if len(children) > 3:
                raise ValueError("非根节点最多只能拥有三个子节点")

            for child in children:
                self._validate_child_direction(parent, child)

    @staticmethod
    def _validate_child_direction(
        parent: LearningTurn,
        child: LearningTurn,
    ) -> None:
        if child.connection_kind == ConnectionKind.CONTINUE:
            if child.parent_port != parent.parent_port:
                raise ValueError("普通后继必须沿当前路径方向继续")
            return

        if child.connection_kind == ConnectionKind.FORK:
            assert parent.parent_port is not None
            if child.parent_port not in parent.parent_port.perpendicular:
                raise ValueError("分支必须相对当前路径转弯")
            return

        raise ValueError("非根子节点不能使用 ROOT 连接类型")

    def _validate_summaries(self) -> None:
        for summary in self.summaries.values():
            if summary.covered_until_turn_id not in self.turns:
                raise ValueError("Summary 覆盖的 Turn 不存在")
            if (
                summary.parent_summary_id is not None
                and summary.parent_summary_id not in self.summaries
            ):
                raise ValueError("Summary 指向不存在的父摘要")

        self._reject_cycles(
            node_ids=set(self.summaries),
            get_parent=lambda summary_id: self.summaries[
                summary_id
            ].parent_summary_id,
            graph_name="Summary",
        )

        for summary in self.summaries.values():
            if summary.parent_summary_id is None:
                continue
            parent = self.summaries[summary.parent_summary_id]
            if not self.is_ancestor(
                parent.covered_until_turn_id,
                summary.covered_until_turn_id,
            ):
                raise ValueError("父摘要覆盖范围不在子摘要路径上")

    def _validate_branches(self) -> None:
        if self.main_branch_id not in self.branches:
            raise ValueError("main_branch_id 指向不存在的 Branch")

        main_branch = self.branches[self.main_branch_id]
        if (
            main_branch.parent_branch_id is not None
            or main_branch.forked_from_turn_id is not None
        ):
            raise ValueError("主 Branch 不能包含父分支或分叉点")

        for branch in self.branches.values():
            if branch.parent_branch_id is not None:
                if branch.parent_branch_id not in self.branches:
                    raise ValueError("Branch 指向不存在的父分支")
                if branch.forked_from_turn_id is None:
                    raise ValueError("子 Branch 必须包含分叉点")
            elif branch.branch_id != self.main_branch_id:
                raise ValueError("只有主 Branch 可以没有父分支")

            if (
                branch.forked_from_turn_id is not None
                and branch.forked_from_turn_id not in self.turns
            ):
                raise ValueError("Branch 的分叉点不存在")
            if (
                branch.head_turn_id is not None
                and branch.head_turn_id not in self.turns
            ):
                raise ValueError("Branch HEAD 不存在")
            if (
                branch.active_summary_id is not None
                and branch.active_summary_id not in self.summaries
            ):
                raise ValueError("Branch 的活动摘要不存在")

            if branch.head_turn_id is not None:
                self._validate_branch_path(branch)
                if branch.active_summary_id is not None:
                    summary = self.summaries[branch.active_summary_id]
                    if not self.is_ancestor(
                        summary.covered_until_turn_id,
                        branch.head_turn_id,
                    ):
                        raise ValueError("活动摘要不属于当前 Branch 路径")

        self._reject_cycles(
            node_ids=set(self.branches),
            get_parent=lambda branch_id: self.branches[
                branch_id
            ].parent_branch_id,
            graph_name="Branch",
        )

    def _validate_branch_path(self, branch: LearningBranch) -> None:
        assert branch.head_turn_id is not None
        if branch.branch_id == self.main_branch_id:
            if self.root_turn_id is None or not self.is_ancestor(
                self.root_turn_id,
                branch.head_turn_id,
            ):
                raise ValueError("主 Branch HEAD 不在根节点路径上")
            current_turn_id = branch.head_turn_id
            while current_turn_id != self.root_turn_id:
                turn = self.turns[current_turn_id]
                if turn.connection_kind != ConnectionKind.CONTINUE:
                    raise ValueError("主 Branch 路径只能包含普通后继")
                assert turn.parent_turn_id is not None
                current_turn_id = turn.parent_turn_id
            return

        assert branch.forked_from_turn_id is not None
        assert branch.parent_branch_id is not None
        parent_branch = self.branches[branch.parent_branch_id]
        if (
            parent_branch.head_turn_id is None
            or not self.is_ancestor(
                branch.forked_from_turn_id,
                parent_branch.head_turn_id,
            )
        ):
            raise ValueError("分叉点不在父 Branch 路径上")
        if not self.is_ancestor(
            branch.forked_from_turn_id,
            branch.head_turn_id,
        ):
            raise ValueError("子 Branch HEAD 不在分叉点之后")

        first_child_id = self.first_child_after(
            branch.forked_from_turn_id,
            branch.head_turn_id,
        )
        if (
            first_child_id is None
            or self.turns[first_child_id].connection_kind
            != ConnectionKind.FORK
        ):
            raise ValueError("子 Branch 的第一条连接必须是分支连接")

    def _validate_citations(self) -> None:
        for citation in self.citations.values():
            if citation.turn_id not in self.turns:
                raise ValueError("Citation 关联的 Turn 不存在")

        for turn in self.turns.values():
            for citation_id in turn.citation_ids:
                if citation_id not in self.citations:
                    raise ValueError("Turn 引用了不存在的 Citation")
                if self.citations[citation_id].turn_id != turn.turn_id:
                    raise ValueError("Citation 必须属于引用它的 Turn")

    def is_ancestor(
        self,
        ancestor_turn_id: str,
        descendant_turn_id: str,
    ) -> bool:
        """判断一个 Turn 是否位于另一个 Turn 的祖先链上。"""
        current_turn_id: Optional[str] = descendant_turn_id
        while current_turn_id is not None:
            if current_turn_id == ancestor_turn_id:
                return True
            current_turn_id = self.turns[current_turn_id].parent_turn_id
        return False

    def first_child_after(
        self,
        ancestor_turn_id: str,
        descendant_turn_id: str,
    ) -> Optional[str]:
        """返回从祖先走向后代时紧邻祖先的第一个子节点。"""
        current_turn_id = descendant_turn_id
        child_turn_id: Optional[str] = None

        while current_turn_id != ancestor_turn_id:
            child_turn_id = current_turn_id
            parent_turn_id = self.turns[current_turn_id].parent_turn_id
            if parent_turn_id is None:
                return None
            current_turn_id = parent_turn_id

        return child_turn_id

    @staticmethod
    def _reject_cycles(
        node_ids: Set[str],
        get_parent: Callable[[str], Optional[str]],
        graph_name: str,
    ) -> None:
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
