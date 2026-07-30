import type { LearningGoal, GoalDraft } from "../domain/models";

export function createLearningGoal(draft: GoalDraft): LearningGoal {
  const goalId = crypto.randomUUID();
  const conversationId = crypto.randomUUID();
  const mainBranchId = crypto.randomUUID();
  const now = new Date().toISOString();

  return {
    goal_id: goalId,
    name: draft.name.trim(),
    stable_context: {
      background: draft.background.trim(),
      learning_goal: draft.learningGoal.trim(),
      target_level: draft.targetLevel.trim(),
      time_budget: draft.timeBudget?.trim() || null,
      constraints: draft.constraints ?? [],
    },
    prompt_snapshot: structuredClone(draft.prompt),
    runtime_model: structuredClone(draft.runtimeModel),
    local_state: {
      conversation: {
        schema_version: 1,
        conversation_id: conversationId,
        revision: 0,
        main_branch_id: mainBranchId,
        root_turn_id: null,
        turns: {},
        branches: {
          [mainBranchId]: {
            branch_id: mainBranchId,
            parent_branch_id: null,
            forked_from_turn_id: null,
            head_turn_id: null,
            active_summary_id: null,
            created_at: now,
          },
        },
        summaries: {},
        citations: {},
      },
      active_branch_id: mainBranchId,
      active_head_turn_id: null,
      applied_operation_ids: [],
    },
    created_at: now,
    updated_at: now,
  };
}
