"""学习问答无状态编排的端到端契约测试。"""

import asyncio
import unittest
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.dependencies import get_learning_turn_orchestrator
from app.exceptions import InvalidLLMConfigurationError
from app.exceptions.learning_errors import LearningGraphRuleError
from app.main import app
from app.learning.application.context_service import LearningContextService
from app.learning.application.path_validator import ActivePathValidator
from app.learning.application.snapshot_adapter import CompactGraphAdapter
from app.learning.application.turn_orchestrator import (
    LearningTurnOrchestrator,
)
from app.learning.contracts.commands import (
    ActivePathContext,
    CompactBranch,
    CompactGraph,
    CompactTurn,
    ConversationAction,
    ConversationCommand,
    PathTurn,
    PromptSnapshot,
    RetrievalMode,
    RuntimeModelConfig,
    StableContext,
)
from app.learning.domain.graph_policy import LearningGraphPolicy
from app.learning.domain.models import ConnectionKind, NodePort
from app.llm.contracts import (
    LLMGenerateResult,
    LLMSource,
    LLMUsage,
    ProviderCapabilities,
)
from app.retrieval.contracts import (
    KnowledgeHit,
    KnowledgeRetrievalResult,
)


NOW = datetime(2026, 7, 30, tzinfo=UTC)


class CharacterTokenEstimator:
    def count_text(self, text: str) -> int:
        return len(text)

    def count_messages(self, messages) -> int:
        return sum(len(message["content"]) for message in messages)


class FakeModelAdapter:
    def __init__(
        self,
        supports_search: bool = True,
        result: LLMGenerateResult | None = None,
        context_window: int = 10000,
        max_output_tokens: int = 1000,
    ) -> None:
        self._capabilities = ProviderCapabilities(
            provider="test-provider",
            supported_models=("test-model",),
            supports_native_search=supports_search,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
        )
        self.result = result or LLMGenerateResult(
            content="模型回答",
            sources=(
                LLMSource(
                    title="官方网页",
                    url="https://example.com/official",
                ),
            ),
            usage=LLMUsage(input_tokens=20, output_tokens=10),
            provider="test-provider",
            model="test-model",
        )
        self.requests = []

    @property
    def capabilities(self):
        return self._capabilities

    async def generate(self, request):
        self.requests.append(request)
        return self.result


class FakeModelFactory:
    def __init__(self, adapter: FakeModelAdapter) -> None:
        self.adapter = adapter
        self.calls = []

    def create(self, provider: str, model: str, api_key: str):
        self.calls.append((provider, model, api_key))
        return self.adapter


class FakeKnowledgeRetriever:
    def __init__(self) -> None:
        self.queries = []

    async def retrieve(self, query: str, limit: int = 6):
        self.queries.append((query, limit))
        return KnowledgeRetrievalResult(
            knowledge_base_version="kb-1",
            hits=(
                KnowledgeHit(
                    chunk_id="chunk-1",
                    document_id="document-1",
                    title="权威资料",
                    content="这是检索到的资料。",
                    url="https://example.com/kb",
                    publisher="官方机构",
                    score=0.9,
                ),
            ),
        )


def stable_context() -> StableContext:
    return StableContext(
        background="零基础",
        learning_goal="学习数学",
        target_level="研究生考试",
    )


def prompt_snapshot() -> PromptSnapshot:
    return PromptSnapshot(
        prompt_id="prompt-1",
        name="默认学习助手",
        source="builtin",
        version=1,
        content="你是一个循序渐进的学习助手。",
    )


def empty_graph() -> CompactGraph:
    return CompactGraph(
        conversation_id="conversation-1",
        revision=0,
        main_branch_id="branch-main",
        branches=(CompactBranch(branch_id="branch-main"),),
    )


def command_for_root(**changes) -> ConversationCommand:
    values = {
        "operation_id": "operation-1",
        "expected_revision": 0,
        "action": ConversationAction.CREATE_ROOT,
        "goal_id": "goal-1",
        "conversation_id": "conversation-1",
        "new_turn_id": "turn-1",
        "user_text": "请生成学习规划",
        "retrieval_mode": RetrievalMode.AUTO,
        "compact_graph": empty_graph(),
        "active_path_context": ActivePathContext(),
        "stable_context": stable_context(),
        "prompt_snapshot": prompt_snapshot(),
        "runtime_model": RuntimeModelConfig(
            provider="test-provider",
            model="test-model",
        ),
    }
    values.update(changes)
    return ConversationCommand(**values)


def vertical_graph() -> CompactGraph:
    return CompactGraph(
        conversation_id="conversation-1",
        revision=2,
        main_branch_id="branch-main",
        root_turn_id="turn-1",
        turns=(
            CompactTurn(
                turn_id="turn-1",
                connection_kind=ConnectionKind.ROOT,
            ),
            CompactTurn(
                turn_id="turn-2",
                parent_turn_id="turn-1",
                connection_kind=ConnectionKind.CONTINUE,
                parent_port=NodePort.BOTTOM,
            ),
        ),
        branches=(
            CompactBranch(
                branch_id="branch-main",
                head_turn_id="turn-2",
            ),
        ),
    )


def vertical_path() -> ActivePathContext:
    return ActivePathContext(
        recent_turns=(
            PathTurn(
                turn_id="turn-1",
                user_content="第一问",
                assistant_content="第一答",
            ),
            PathTurn(
                turn_id="turn-2",
                parent_turn_id="turn-1",
                user_content="第二问",
                assistant_content="第二答",
            ),
        )
    )


def build_orchestrator(
    adapter: FakeModelAdapter | None = None,
):
    selected_adapter = adapter or FakeModelAdapter()
    factory = FakeModelFactory(selected_adapter)
    retriever = FakeKnowledgeRetriever()
    orchestrator = LearningTurnOrchestrator(
        graph_adapter=CompactGraphAdapter(),
        graph_policy=LearningGraphPolicy(),
        path_validator=ActivePathValidator(),
        context_service=LearningContextService(
            token_estimator=CharacterTokenEstimator(),
            safety_margin=100,
        ),
        model_factory=factory,
        knowledge_retriever=retriever,
    )
    return orchestrator, factory, retriever, selected_adapter


class LearningTurnOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_root_turn_returns_atomic_delta_and_citations(self) -> None:
        orchestrator, factory, retriever, adapter = build_orchestrator()

        delta = await orchestrator.execute(
            command_for_root(),
            api_key="runtime-secret",
        )

        self.assertEqual(delta.old_revision, 0)
        self.assertEqual(delta.new_revision, 1)
        self.assertEqual(delta.added_turns[0].turn_id, "turn-1")
        self.assertEqual(delta.added_turns[0].parent_turn_id, None)
        self.assertEqual(len(delta.added_citations), 2)
        self.assertEqual(
            factory.calls,
            [("test-provider", "test-model", "runtime-secret")],
        )
        self.assertEqual(retriever.queries, [("请生成学习规划", 6)])
        self.assertEqual(adapter.requests[0].web_search.value, "auto")

    async def test_append_updates_existing_branch_head(self) -> None:
        orchestrator, _, _, _ = build_orchestrator()
        command = ConversationCommand(
            operation_id="operation-3",
            expected_revision=2,
            action=ConversationAction.APPEND_TURN,
            goal_id="goal-1",
            conversation_id="conversation-1",
            new_turn_id="turn-3",
            source_turn_id="turn-2",
            active_branch_id="branch-main",
            user_text="第三问",
            compact_graph=vertical_graph(),
            active_path_context=vertical_path(),
            stable_context=stable_context(),
            prompt_snapshot=prompt_snapshot(),
            runtime_model=RuntimeModelConfig(
                provider="test-provider",
                model="test-model",
            ),
        )

        delta = await orchestrator.execute(command, api_key="secret")

        self.assertEqual(
            delta.added_turns[0].connection_kind,
            ConnectionKind.CONTINUE,
        )
        self.assertEqual(
            delta.branch_head_updates[0].old_head_turn_id,
            "turn-2",
        )
        self.assertEqual(delta.next_active_branch_id, "branch-main")

    async def test_fork_creates_new_branch_and_turns_right(self) -> None:
        orchestrator, _, _, _ = build_orchestrator()
        command = ConversationCommand(
            operation_id="operation-fork",
            expected_revision=2,
            action=ConversationAction.FORK_FROM_TURN,
            goal_id="goal-1",
            conversation_id="conversation-1",
            new_turn_id="turn-right",
            source_turn_id="turn-2",
            active_branch_id="branch-main",
            new_branch_id="branch-right",
            user_text="从这里深入学习",
            compact_graph=vertical_graph(),
            active_path_context=vertical_path(),
            stable_context=stable_context(),
            prompt_snapshot=prompt_snapshot(),
            runtime_model=RuntimeModelConfig(
                provider="test-provider",
                model="test-model",
            ),
        )

        delta = await orchestrator.execute(command, api_key="secret")

        self.assertEqual(delta.added_turns[0].parent_port, NodePort.RIGHT)
        self.assertEqual(
            delta.added_turns[0].connection_kind,
            ConnectionKind.FORK,
        )
        self.assertEqual(delta.added_branches[0].branch_id, "branch-right")
        self.assertEqual(delta.next_active_branch_id, "branch-right")

    async def test_required_web_rejects_unsupported_model(self) -> None:
        adapter = FakeModelAdapter(supports_search=False)
        orchestrator, _, retriever, _ = build_orchestrator(adapter)
        command = command_for_root(
            retrieval_mode=RetrievalMode.WEB_ONLY
        )

        with self.assertRaisesRegex(
            InvalidLLMConfigurationError,
            "不支持",
        ):
            await orchestrator.execute(command, api_key="secret")

        self.assertEqual(retriever.queries, [])

    async def test_missing_ancestor_path_is_rejected_before_model(self) -> None:
        orchestrator, _, _, adapter = build_orchestrator()
        command = ConversationCommand(
            operation_id="operation-invalid-path",
            expected_revision=2,
            action=ConversationAction.APPEND_TURN,
            goal_id="goal-1",
            conversation_id="conversation-1",
            new_turn_id="turn-3",
            source_turn_id="turn-2",
            active_branch_id="branch-main",
            user_text="第三问",
            compact_graph=vertical_graph(),
            active_path_context=ActivePathContext(
                recent_turns=(
                    PathTurn(
                        turn_id="turn-2",
                        parent_turn_id="turn-1",
                        user_content="第二问",
                        assistant_content="第二答",
                    ),
                )
            ),
            stable_context=stable_context(),
            prompt_snapshot=prompt_snapshot(),
            runtime_model=RuntimeModelConfig(
                provider="test-provider",
                model="test-model",
            ),
        )

        with self.assertRaisesRegex(LearningGraphRuleError, "缺失"):
            await orchestrator.execute(command, api_key="secret")

        self.assertEqual(adapter.requests, [])

    async def test_long_path_creates_summary_before_main_call(self) -> None:
        turns = []
        path_turns = []
        for index in range(1, 6):
            turn_id = f"turn-{index}"
            parent_id = f"turn-{index - 1}" if index > 1 else None
            turns.append(
                CompactTurn(
                    turn_id=turn_id,
                    parent_turn_id=parent_id,
                    connection_kind=(
                        ConnectionKind.ROOT
                        if index == 1
                        else ConnectionKind.CONTINUE
                    ),
                    parent_port=(
                        None if index == 1 else NodePort.BOTTOM
                    ),
                )
            )
            path_turns.append(
                PathTurn(
                    turn_id=turn_id,
                    parent_turn_id=parent_id,
                    user_content="问" * 60,
                    assistant_content="答" * 60,
                )
            )

        graph = CompactGraph(
            conversation_id="conversation-1",
            revision=5,
            main_branch_id="branch-main",
            root_turn_id="turn-1",
            turns=tuple(turns),
            branches=(
                CompactBranch(
                    branch_id="branch-main",
                    head_turn_id="turn-5",
                ),
            ),
        )
        command = ConversationCommand(
            operation_id="operation-compress",
            expected_revision=5,
            action=ConversationAction.APPEND_TURN,
            goal_id="goal-1",
            conversation_id="conversation-1",
            new_turn_id="turn-6",
            source_turn_id="turn-5",
            active_branch_id="branch-main",
            user_text="继续",
            compact_graph=graph,
            active_path_context=ActivePathContext(
                recent_turns=tuple(path_turns)
            ),
            stable_context=stable_context(),
            prompt_snapshot=prompt_snapshot(),
            runtime_model=RuntimeModelConfig(
                provider="test-provider",
                model="test-model",
            ),
        )
        adapter = FakeModelAdapter(
            context_window=900,
            max_output_tokens=100,
        )
        orchestrator, _, _, _ = build_orchestrator(adapter)

        delta = await orchestrator.execute(command, api_key="secret")

        self.assertEqual(len(adapter.requests), 2)
        self.assertEqual(len(delta.added_summaries), 1)
        self.assertEqual(
            delta.added_summaries[0].covered_until_turn_id,
            "turn-2",
        )


class FakeRouteOrchestrator:
    def __init__(self, delta) -> None:
        self.delta = delta
        self.calls = []

    async def execute(self, command, api_key):
        self.calls.append((command, api_key))
        return self.delta


class LearningRouteTests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_route_passes_header_key_without_persisting_it(self) -> None:
        orchestrator, _, _, _ = build_orchestrator()
        delta = asyncio.run(
            orchestrator.execute(
                command_for_root(),
                api_key="prepare-secret",
            )
        )
        fake = FakeRouteOrchestrator(delta)
        app.dependency_overrides[get_learning_turn_orchestrator] = (
            lambda: fake
        )

        response = TestClient(app).post(
            "/learning/conversations/turns",
            headers={"X-Provider-API-Key": "runtime-secret"},
            json=command_for_root().model_dump(mode="json"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake.calls[0][1], "runtime-secret")
        self.assertNotIn(
            "runtime-secret",
            response.text,
        )

    def test_route_requires_api_key_header(self) -> None:
        response = TestClient(app).post(
            "/learning/conversations/turns",
            json=command_for_root().model_dump(mode="json"),
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
