import type {
  ConversationAction,
  ConversationCommand,
  NodePort,
  RetrievalMode,
  SummaryVersion,
} from "../../../shared/contracts/learning";
import type { LearningGoal } from "../../goals/domain/models";
import { findSourceBranch, turnPath } from "./graphSelectors";

export interface BuildCommandInput {
  goal: LearningGoal;
  userText: string;
  sourceTurnId?: string;
  sourceBranchId?: string;
  forceFork?: boolean;
  preferredPort?: NodePort;
  retrievalMode?: RetrievalMode;
}

export function buildConversationCommand(
  input: BuildCommandInput,
): ConversationCommand {
  const { goal } = input;
  const conversation = goal.local_state.conversation;
  const isRoot = conversation.root_turn_id === null;
  const sourceTurnId = isRoot
    ? null
    : input.sourceTurnId ?? goal.local_state.active_head_turn_id;
  if (!isRoot && !sourceTurnId) {
    throw new Error("非空会话缺少当前节点");
  }

  const sourceBranch = sourceTurnId
    ? findSourceBranch(
        conversation,
        sourceTurnId,
        input.sourceBranchId ?? goal.local_state.active_branch_id,
      )
    : null;
  const action = resolveAction(
    isRoot,
    sourceTurnId,
    sourceBranch?.head_turn_id ?? null,
    input.forceFork ?? false,
  );
  const newBranchId =
    action === "fork_from_turn" ? crypto.randomUUID() : null;

  return {
    operation_id: crypto.randomUUID(),
    expected_revision: conversation.revision,
    action,
    goal_id: goal.goal_id,
    conversation_id: conversation.conversation_id,
    new_turn_id: crypto.randomUUID(),
    source_turn_id: sourceTurnId,
    active_branch_id: sourceBranch?.branch_id ?? null,
    new_branch_id: newBranchId,
    preferred_port:
      action === "fork_from_turn"
        ? input.preferredPort ?? null
        : null,
    user_text: input.userText.trim(),
    retrieval_mode: input.retrievalMode ?? "auto",
    compact_graph: {
      schema_version: 1,
      conversation_id: conversation.conversation_id,
      revision: conversation.revision,
      main_branch_id: conversation.main_branch_id,
      root_turn_id: conversation.root_turn_id,
      turns: Object.values(conversation.turns).map((turn) => ({
        turn_id: turn.turn_id,
        parent_turn_id: turn.parent_turn_id,
        connection_kind: turn.connection_kind,
        parent_port: turn.parent_port,
      })),
      branches: Object.values(conversation.branches).map((branch) => ({
        branch_id: branch.branch_id,
        parent_branch_id: branch.parent_branch_id,
        forked_from_turn_id: branch.forked_from_turn_id,
        head_turn_id: branch.head_turn_id,
        active_summary_id: branch.active_summary_id,
      })),
    },
    active_path_context: buildPathContext(
      goal,
      sourceTurnId,
      sourceBranch?.active_summary_id ?? null,
    ),
    stable_context: goal.stable_context,
    prompt_snapshot: goal.prompt_snapshot,
    runtime_model: goal.runtime_model,
  };
}

function resolveAction(
  isRoot: boolean,
  sourceTurnId: string | null,
  branchHeadTurnId: string | null,
  forceFork: boolean,
): ConversationAction {
  if (isRoot) {
    return "create_root";
  }
  if (forceFork || sourceTurnId !== branchHeadTurnId) {
    return "fork_from_turn";
  }
  return "append_turn";
}

function buildPathContext(
  goal: LearningGoal,
  sourceTurnId: string | null,
  activeSummaryId: string | null,
): ConversationCommand["active_path_context"] {
  if (!sourceTurnId) {
    return { summary: null, recent_turns: [] };
  }
  const conversation = goal.local_state.conversation;
  const path = turnPath(conversation, sourceTurnId);
  let summary: SummaryVersion | null = activeSummaryId
    ? conversation.summaries[activeSummaryId] ?? null
    : null;
  let startIndex = 0;
  if (summary) {
    const coveredIndex = path.findIndex(
      (turn) => turn.turn_id === summary?.covered_until_turn_id,
    );
    if (coveredIndex < 0) {
      summary = null;
    } else {
      startIndex = coveredIndex + 1;
    }
  }
  return {
    summary,
    recent_turns: path.slice(startIndex).map((turn) => ({
      turn_id: turn.turn_id,
      parent_turn_id: turn.parent_turn_id,
      user_content: turn.user_content,
      assistant_content: turn.assistant_content,
    })),
  };
}
