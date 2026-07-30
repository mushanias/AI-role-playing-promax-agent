import type {
  LearningConversation,
  PromptSnapshot,
  RuntimeModelConfig,
  StableContext,
} from "../../../shared/contracts/learning";

/** 浏览器本地拥有的会话状态；API Key 永远不属于此模型。 */
export interface LocalConversationState {
  conversation: LearningConversation;
  active_branch_id: string;
  active_head_turn_id: string | null;
  applied_operation_ids: string[];
}

export interface LearningGoal {
  goal_id: string;
  name: string;
  stable_context: StableContext;
  prompt_snapshot: PromptSnapshot;
  runtime_model: RuntimeModelConfig;
  local_state: LocalConversationState;
  created_at: string;
  updated_at: string;
}

export interface GoalDraft {
  name: string;
  background: string;
  learningGoal: string;
  targetLevel: string;
  timeBudget?: string;
  constraints?: string[];
  prompt: PromptSnapshot;
  runtimeModel: RuntimeModelConfig;
}
