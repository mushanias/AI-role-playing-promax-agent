import type { ConversationDelta } from "../../../shared/contracts/learning";
import { createLearningGoal } from "../application/createGoal";
import { BUILTIN_LEARNING_PROMPTS } from "../application/prompts";
import {
  GoalRepository,
  LocalRevisionConflictError,
} from "./goalRepository";

function createGoal() {
  return createLearningGoal({
    name: "测试目标",
    background: "已有基础",
    learningGoal: "掌握主题",
    targetLevel: "能够独立应用",
    prompt: BUILTIN_LEARNING_PROMPTS[0],
    runtimeModel: {
      provider: "openai",
      model: "gpt-5.6",
    },
  });
}

function rootDelta(goal: ReturnType<typeof createGoal>): ConversationDelta {
  const turnId = crypto.randomUUID();
  return {
    operation_id: crypto.randomUUID(),
    old_revision: 0,
    new_revision: 1,
    added_turns: [
      {
        turn_id: turnId,
        parent_turn_id: null,
        connection_kind: "root",
        parent_port: null,
        user_content: "请规划",
        assistant_content: "这是规划",
        citation_ids: [],
        provider: "openai",
        model: "gpt-5.6",
        created_at: new Date().toISOString(),
      },
    ],
    added_branches: [],
    added_summaries: [],
    added_citations: [],
    branch_head_updates: [
      {
        branch_id:
          goal.local_state.conversation.main_branch_id,
        old_head_turn_id: null,
        new_head_turn_id: turnId,
        new_active_summary_id: null,
      },
    ],
    next_active_branch_id:
      goal.local_state.conversation.main_branch_id,
    next_active_head_turn_id: turnId,
    warnings: [],
    usage: {},
  };
}

describe("GoalRepository", () => {
  let repository: GoalRepository;
  let databaseName: string;

  beforeEach(() => {
    databaseName = `test-${crypto.randomUUID()}`;
    repository = new GoalRepository(databaseName);
  });

  afterEach(async () => {
    await repository.close();
    indexedDB.deleteDatabase(databaseName);
  });

  it("原子应用增量并支持相同操作幂等重放", async () => {
    const goal = createGoal();
    const delta = rootDelta(goal);
    await repository.save(goal);

    const first = await repository.applyDelta(goal.goal_id, delta);
    const second = await repository.applyDelta(goal.goal_id, delta);

    expect(first.local_state.conversation.revision).toBe(1);
    expect(first.local_state.conversation.root_turn_id).toBe(
      delta.next_active_head_turn_id,
    );
    expect(Object.keys(second.local_state.conversation.turns)).toHaveLength(
      1,
    );
    expect(second.local_state.applied_operation_ids).toEqual([
      delta.operation_id,
    ]);
  });

  it("拒绝把旧修订号的增量写入新状态", async () => {
    const goal = createGoal();
    const delta = rootDelta(goal);
    await repository.save(goal);
    await repository.applyDelta(goal.goal_id, delta);

    await expect(
      repository.applyDelta(goal.goal_id, {
        ...delta,
        operation_id: crypto.randomUUID(),
      }),
    ).rejects.toBeInstanceOf(LocalRevisionConflictError);
  });
});
