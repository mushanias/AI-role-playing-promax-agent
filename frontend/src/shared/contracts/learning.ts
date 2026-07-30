/** 与后端学习模块一一对应的稳定传输契约。 */

export type NodePort = "top" | "right" | "bottom" | "left";
export type ConnectionKind = "root" | "continue" | "fork";
export type ConversationAction =
  | "create_root"
  | "append_turn"
  | "fork_from_turn";
export type RetrievalMode =
  | "auto"
  | "knowledge_base_only"
  | "web_only"
  | "knowledge_base_and_web";

export interface StableContext {
  background: string;
  learning_goal: string;
  target_level: string;
  time_budget: string | null;
  constraints: string[];
}

export interface PromptSnapshot {
  prompt_id: string;
  name: string;
  source: "builtin" | "custom";
  version: number;
  content: string;
}

export interface RuntimeModelConfig {
  provider: string;
  model: string;
}

export interface LearningTurn {
  turn_id: string;
  parent_turn_id: string | null;
  connection_kind: ConnectionKind;
  parent_port: NodePort | null;
  user_content: string;
  assistant_content: string;
  citation_ids: string[];
  provider: string;
  model: string;
  created_at: string;
}

export interface LearningBranch {
  branch_id: string;
  parent_branch_id: string | null;
  forked_from_turn_id: string | null;
  head_turn_id: string | null;
  active_summary_id: string | null;
  created_at: string;
}

export interface SummaryVersion {
  summary_id: string;
  parent_summary_id: string | null;
  covered_until_turn_id: string;
  path_fingerprint: string;
  content: string;
  learning_plan_state: string | null;
  completed_items: string[];
  current_item: string | null;
  user_decisions: string[];
  unresolved_questions: string[];
  created_at: string;
}

export interface Citation {
  citation_id: string;
  turn_id: string;
  source: "knowledge_base" | "web";
  title: string;
  url: string | null;
  publisher: string | null;
  published_at: string | null;
  retrieved_at: string;
  knowledge_base_version: string | null;
  reference_id: string | null;
}

export interface LearningConversation {
  schema_version: 1;
  conversation_id: string;
  revision: number;
  main_branch_id: string;
  root_turn_id: string | null;
  turns: Record<string, LearningTurn>;
  branches: Record<string, LearningBranch>;
  summaries: Record<string, SummaryVersion>;
  citations: Record<string, Citation>;
}

export interface BranchHeadUpdate {
  branch_id: string;
  old_head_turn_id: string | null;
  new_head_turn_id: string;
  new_active_summary_id: string | null;
}

export interface ConversationDelta {
  operation_id: string;
  old_revision: number;
  new_revision: number;
  added_turns: LearningTurn[];
  added_branches: LearningBranch[];
  added_summaries: SummaryVersion[];
  added_citations: Citation[];
  branch_head_updates: BranchHeadUpdate[];
  next_active_branch_id: string;
  next_active_head_turn_id: string;
  warnings: string[];
  usage: Record<string, number>;
}

export interface ConversationCommand {
  operation_id: string;
  expected_revision: number;
  action: ConversationAction;
  goal_id: string;
  conversation_id: string;
  new_turn_id: string;
  source_turn_id: string | null;
  active_branch_id: string | null;
  new_branch_id: string | null;
  preferred_port: NodePort | null;
  user_text: string;
  retrieval_mode: RetrievalMode;
  compact_graph: {
    schema_version: 1;
    conversation_id: string;
    revision: number;
    main_branch_id: string;
    root_turn_id: string | null;
    turns: Array<
      Pick<
        LearningTurn,
        | "turn_id"
        | "parent_turn_id"
        | "connection_kind"
        | "parent_port"
      >
    >;
    branches: Array<
      Pick<
        LearningBranch,
        | "branch_id"
        | "parent_branch_id"
        | "forked_from_turn_id"
        | "head_turn_id"
        | "active_summary_id"
      >
    >;
  };
  active_path_context: {
    summary: SummaryVersion | null;
    recent_turns: Array<
      Pick<
        LearningTurn,
        | "turn_id"
        | "parent_turn_id"
        | "user_content"
        | "assistant_content"
      >
    >;
  };
  stable_context: StableContext;
  prompt_snapshot: PromptSnapshot;
  runtime_model: RuntimeModelConfig;
}
