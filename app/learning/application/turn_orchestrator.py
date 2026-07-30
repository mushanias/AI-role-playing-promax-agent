"""一次学习问答从图验证到增量返回的无状态编排。"""

import hashlib
import time
from datetime import UTC, datetime

from app.exceptions import InvalidLLMConfigurationError
from app.exceptions.learning_errors import LearningGraphRuleError
from app.learning.application.context_service import LearningContextService
from app.learning.application.path_validator import ActivePathValidator
from app.learning.application.snapshot_adapter import CompactGraphAdapter
from app.learning.contracts.commands import (
    ConversationAction,
    ConversationCommand,
    RetrievalMode,
)
from app.learning.contracts.delta import (
    BranchHeadUpdate,
    ConversationDelta,
)
from app.learning.domain.graph_policy import LearningGraphPolicy
from app.learning.domain.models import (
    Citation,
    CitationSource,
    LearningBranch,
    LearningConversation,
    LearningTurn,
    SummaryVersion,
)
from app.learning.observability import (
    LearningOperationEvent,
    LearningOperationObserver,
    LearningStage,
)
from app.llm.contracts import (
    LLMAdapterFactory,
    LLMGenerateRequest,
    LLMSource,
    WebSearchPolicy,
)
from app.retrieval.contracts import (
    KnowledgeHit,
    KnowledgeRetrievalResult,
    KnowledgeRetriever,
)


class LearningTurnOrchestrator:
    """只依赖能力契约编排正式问答，不保存用户会话。"""

    def __init__(
        self,
        graph_adapter: CompactGraphAdapter,
        graph_policy: LearningGraphPolicy,
        path_validator: ActivePathValidator,
        context_service: LearningContextService,
        model_factory: LLMAdapterFactory,
        knowledge_retriever: KnowledgeRetriever,
        observer: LearningOperationObserver | None = None,
    ) -> None:
        self.graph_adapter = graph_adapter
        self.graph_policy = graph_policy
        self.path_validator = path_validator
        self.context_service = context_service
        self.model_factory = model_factory
        self.knowledge_retriever = knowledge_retriever
        self.observer = observer

    async def execute(
        self,
        command: ConversationCommand,
        api_key: str,
    ) -> ConversationDelta:
        """执行一次完整非流式问答，失败时不返回部分 Delta。"""
        stage_started = time.perf_counter()
        conversation = self.graph_adapter.to_conversation(
            command.compact_graph
        )
        self._validate_new_ids(command, conversation)
        placement = self.graph_policy.plan(
            conversation=conversation,
            action=command.action,
            source_turn_id=command.source_turn_id,
            branch_id=command.active_branch_id,
            preferred_port=command.preferred_port,
        )
        self.path_validator.validate(
            conversation=conversation,
            action=command.action,
            source_turn_id=command.source_turn_id,
            path=command.active_path_context,
        )
        self._record(
            command,
            LearningStage.VALIDATION,
            stage_started,
        )

        model = self.model_factory.create(
            provider=command.runtime_model.provider,
            model=command.runtime_model.model,
            api_key=api_key,
        )
        web_policy, routing_warnings = self._web_policy(
            command.retrieval_mode,
            model.capabilities.supports_native_search,
            command.runtime_model.provider,
        )

        stage_started = time.perf_counter()
        retrieval = await self._retrieve(
            command.retrieval_mode,
            command.user_text,
        )
        self._record(
            command,
            LearningStage.RETRIEVAL,
            stage_started,
            retrieval_hits=len(retrieval.hits),
            warning_count=len(retrieval.warnings),
        )

        stage_started = time.perf_counter()
        prepared = await self.context_service.prepare(
            command=command,
            retrieval=retrieval,
            model=model,
        )
        self._record(
            command,
            LearningStage.CONTEXT,
            stage_started,
            warning_count=len(prepared.warnings),
        )

        stage_started = time.perf_counter()
        model_result = await model.generate(
            LLMGenerateRequest(
                messages=prepared.messages,
                web_search=web_policy,
            )
        )
        self._record(
            command,
            LearningStage.MODEL,
            stage_started,
            warning_count=len(model_result.warnings),
        )

        now = datetime.now(UTC)
        citations = self._build_citations(
            turn_id=command.new_turn_id,
            knowledge_hits=prepared.used_knowledge_hits,
            knowledge_base_version=retrieval.knowledge_base_version,
            web_sources=model_result.sources,
            retrieved_at=now,
        )
        new_turn = LearningTurn(
            turn_id=command.new_turn_id,
            parent_turn_id=placement.parent_turn_id,
            connection_kind=placement.connection_kind,
            parent_port=placement.parent_port,
            user_content=command.user_text,
            assistant_content=model_result.content,
            citation_ids=tuple(
                citation.citation_id for citation in citations
            ),
            provider=model_result.provider,
            model=model_result.model,
            created_at=now,
        )
        delta = self._build_delta(
            command=command,
            new_turn=new_turn,
            citations=citations,
            added_summary=prepared.added_summary,
            warnings=(
                *routing_warnings,
                *prepared.warnings,
                *model_result.warnings,
            ),
            usage={
                "input_tokens": model_result.usage.input_tokens,
                "output_tokens": model_result.usage.output_tokens,
            },
            created_at=now,
        )
        self._record(
            command,
            LearningStage.COMPLETE,
            stage_started,
            retrieval_hits=len(prepared.used_knowledge_hits),
            warning_count=len(delta.warnings),
        )
        return delta

    @staticmethod
    def _validate_new_ids(
        command: ConversationCommand,
        conversation: LearningConversation,
    ) -> None:
        if command.new_turn_id in conversation.turns:
            raise LearningGraphRuleError("new_turn_id 已经存在")
        if (
            command.new_branch_id is not None
            and command.new_branch_id in conversation.branches
        ):
            raise LearningGraphRuleError("new_branch_id 已经存在")

    async def _retrieve(
        self,
        mode: RetrievalMode,
        query: str,
    ) -> KnowledgeRetrievalResult:
        if mode == RetrievalMode.WEB_ONLY:
            return KnowledgeRetrievalResult(
                knowledge_base_version="not_requested"
            )
        return await self.knowledge_retriever.retrieve(
            query=query,
            limit=6,
        )

    @staticmethod
    def _web_policy(
        mode: RetrievalMode,
        supports_native_search: bool,
        provider: str,
    ) -> tuple[WebSearchPolicy, tuple[str, ...]]:
        if mode == RetrievalMode.KNOWLEDGE_BASE_ONLY:
            return WebSearchPolicy.DISABLED, ()

        if mode in (
            RetrievalMode.WEB_ONLY,
            RetrievalMode.KNOWLEDGE_BASE_AND_WEB,
        ):
            if not supports_native_search:
                raise InvalidLLMConfigurationError(
                    f"{provider} 不支持原生联网搜索"
                )
            return WebSearchPolicy.REQUIRED, ()

        if supports_native_search:
            return WebSearchPolicy.AUTO, ()
        return (
            WebSearchPolicy.DISABLED,
            ("当前模型不支持联网搜索，自动模式已仅使用公共知识库",),
        )

    def _build_delta(
        self,
        command: ConversationCommand,
        new_turn: LearningTurn,
        citations: tuple[Citation, ...],
        added_summary: SummaryVersion | None,
        warnings: tuple[str, ...],
        usage: dict[str, int],
        created_at: datetime,
    ) -> ConversationDelta:
        summary_id = (
            added_summary.summary_id
            if added_summary is not None
            else (
                command.active_path_context.summary.summary_id
                if command.active_path_context.summary is not None
                else None
            )
        )
        summaries = (added_summary,) if added_summary is not None else ()

        if command.action == ConversationAction.FORK_FROM_TURN:
            assert command.new_branch_id is not None
            assert command.active_branch_id is not None
            new_branch = LearningBranch(
                branch_id=command.new_branch_id,
                parent_branch_id=command.active_branch_id,
                forked_from_turn_id=command.source_turn_id,
                head_turn_id=new_turn.turn_id,
                active_summary_id=summary_id,
                created_at=created_at,
            )
            added_branches = (new_branch,)
            head_updates = ()
            next_branch_id = new_branch.branch_id
        else:
            branch_id = (
                command.compact_graph.main_branch_id
                if command.action == ConversationAction.CREATE_ROOT
                else command.active_branch_id
            )
            assert branch_id is not None
            previous_head = (
                None
                if command.action == ConversationAction.CREATE_ROOT
                else command.source_turn_id
            )
            added_branches = ()
            head_updates = (
                BranchHeadUpdate(
                    branch_id=branch_id,
                    old_head_turn_id=previous_head,
                    new_head_turn_id=new_turn.turn_id,
                    new_active_summary_id=summary_id,
                ),
            )
            next_branch_id = branch_id

        return ConversationDelta(
            operation_id=command.operation_id,
            old_revision=command.expected_revision,
            new_revision=command.expected_revision + 1,
            added_turns=(new_turn,),
            added_branches=added_branches,
            added_summaries=summaries,
            added_citations=citations,
            branch_head_updates=head_updates,
            next_active_branch_id=next_branch_id,
            next_active_head_turn_id=new_turn.turn_id,
            warnings=tuple(dict.fromkeys(warnings)),
            usage=usage,
        )

    @classmethod
    def _build_citations(
        cls,
        turn_id: str,
        knowledge_hits: tuple[KnowledgeHit, ...],
        knowledge_base_version: str,
        web_sources: tuple[LLMSource, ...],
        retrieved_at: datetime,
    ) -> tuple[Citation, ...]:
        citations: list[Citation] = []
        for hit in knowledge_hits:
            citations.append(
                Citation(
                    citation_id=cls._citation_id(
                        turn_id,
                        "kb",
                        hit.chunk_id,
                    ),
                    turn_id=turn_id,
                    source=CitationSource.KNOWLEDGE_BASE,
                    title=hit.title,
                    url=hit.url,
                    publisher=hit.publisher,
                    published_at=hit.published_at,
                    retrieved_at=retrieved_at,
                    knowledge_base_version=knowledge_base_version,
                    reference_id=hit.chunk_id,
                )
            )
        for source in web_sources:
            citations.append(
                Citation(
                    citation_id=cls._citation_id(
                        turn_id,
                        "web",
                        source.url,
                    ),
                    turn_id=turn_id,
                    source=CitationSource.WEB,
                    title=source.title,
                    url=source.url,
                    publisher=source.publisher,
                    retrieved_at=retrieved_at,
                )
            )
        return tuple(citations)

    @staticmethod
    def _citation_id(
        turn_id: str,
        source: str,
        reference: str,
    ) -> str:
        digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16]
        return f"{turn_id}-{source}-{digest}"

    def _record(
        self,
        command: ConversationCommand,
        stage: LearningStage,
        stage_started: float,
        retrieval_hits: int = 0,
        warning_count: int = 0,
    ) -> None:
        if self.observer is None:
            return
        try:
            self.observer.record(
                LearningOperationEvent(
                    operation_id=command.operation_id,
                    goal_id=command.goal_id,
                    conversation_id=command.conversation_id,
                    turn_id=command.new_turn_id,
                    provider=command.runtime_model.provider,
                    model=command.runtime_model.model,
                    stage=stage,
                    elapsed_seconds=time.perf_counter() - stage_started,
                    retrieval_hits=retrieval_hits,
                    warning_count=warning_count,
                )
            )
        except Exception:
            return
