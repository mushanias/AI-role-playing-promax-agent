import type {
  LearningConversation,
  NodePort,
} from "../../../shared/contracts/learning";

export interface TurnPosition {
  x: number;
  y: number;
}

const HORIZONTAL_STEP = 500;
const VERTICAL_STEP = 340;

const direction: Record<NodePort, TurnPosition> = {
  top: { x: 0, y: -VERTICAL_STEP },
  right: { x: HORIZONTAL_STEP, y: 0 },
  bottom: { x: 0, y: VERTICAL_STEP },
  left: { x: -HORIZONTAL_STEP, y: 0 },
};

/** 按端口语义稳定排布；坐标冲突时只沿原方向加长，不改变转弯含义。 */
export function layoutConversation(
  conversation: LearningConversation,
): Record<string, TurnPosition> {
  if (!conversation.root_turn_id) {
    return {};
  }
  const positions: Record<string, TurnPosition> = {
    [conversation.root_turn_id]: { x: 0, y: 0 },
  };
  const occupied = new Set(["0:0"]);
  const children = new Map<string, string[]>();
  for (const turn of Object.values(conversation.turns)) {
    if (!turn.parent_turn_id) {
      continue;
    }
    const list = children.get(turn.parent_turn_id) ?? [];
    list.push(turn.turn_id);
    children.set(turn.parent_turn_id, list);
  }
  for (const list of children.values()) {
    list.sort((left, right) =>
      conversation.turns[left].created_at.localeCompare(
        conversation.turns[right].created_at,
      ),
    );
  }

  const queue = [conversation.root_turn_id];
  while (queue.length) {
    const parentId = queue.shift()!;
    const parentPosition = positions[parentId];
    for (const childId of children.get(parentId) ?? []) {
      const port =
        conversation.turns[childId].parent_port ?? "bottom";
      const offset = direction[port];
      let multiplier = 1;
      let position = {
        x: parentPosition.x + offset.x,
        y: parentPosition.y + offset.y,
      };
      while (occupied.has(`${position.x}:${position.y}`)) {
        multiplier += 1;
        position = {
          x: parentPosition.x + offset.x * multiplier,
          y: parentPosition.y + offset.y * multiplier,
        };
      }
      positions[childId] = position;
      occupied.add(`${position.x}:${position.y}`);
      queue.push(childId);
    }
  }
  return positions;
}
