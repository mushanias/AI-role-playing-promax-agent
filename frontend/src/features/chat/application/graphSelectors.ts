import type {
  LearningBranch,
  LearningConversation,
  LearningTurn,
  NodePort,
} from "../../../shared/contracts/learning";

export function turnPath(
  conversation: LearningConversation,
  turnId: string,
): LearningTurn[] {
  const reversed: LearningTurn[] = [];
  let currentId: string | null = turnId;
  const visited = new Set<string>();
  while (currentId) {
    if (visited.has(currentId)) {
      throw new Error("节点历史中存在循环");
    }
    visited.add(currentId);
    const turn: LearningTurn | undefined =
      conversation.turns[currentId];
    if (!turn) {
      throw new Error(`节点 ${currentId} 不存在`);
    }
    reversed.push(turn);
    currentId = turn.parent_turn_id;
  }
  return reversed.reverse();
}

export function branchContainsTurn(
  conversation: LearningConversation,
  branch: LearningBranch,
  turnId: string,
): boolean {
  if (!branch.head_turn_id) {
    return false;
  }
  return turnPath(conversation, branch.head_turn_id).some(
    (turn) => turn.turn_id === turnId,
  );
}

export function findSourceBranch(
  conversation: LearningConversation,
  turnId: string,
  preferredBranchId?: string,
): LearningBranch {
  const preferred = preferredBranchId
    ? conversation.branches[preferredBranchId]
    : undefined;
  if (preferred?.head_turn_id === turnId) {
    return preferred;
  }
  const exactHead = Object.values(conversation.branches).find(
    (item) => item.head_turn_id === turnId,
  );
  if (exactHead) {
    return exactHead;
  }
  if (
    preferred &&
    branchContainsTurn(conversation, preferred, turnId)
  ) {
    return preferred;
  }
  const branch = Object.values(conversation.branches).find((item) =>
    branchContainsTurn(conversation, item, turnId),
  );
  if (!branch) {
    throw new Error("当前节点不属于任何分支");
  }
  return branch;
}

export function occupiedChildPorts(
  conversation: LearningConversation,
  turnId: string,
): Set<NodePort> {
  return new Set(
    Object.values(conversation.turns)
      .filter((turn) => turn.parent_turn_id === turnId)
      .map((turn) => turn.parent_port)
      .filter((port): port is NodePort => port !== null),
  );
}
