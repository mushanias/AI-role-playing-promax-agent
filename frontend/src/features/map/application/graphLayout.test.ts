import type { LearningConversation } from "../../../shared/contracts/learning";
import { layoutConversation } from "./graphLayout";

describe("layoutConversation", () => {
  it("让分支转弯且不把节点排到相同坐标", () => {
    const now = new Date().toISOString();
    const conversation: LearningConversation = {
      schema_version: 1,
      conversation_id: "conversation",
      revision: 4,
      main_branch_id: "main",
      root_turn_id: "root",
      turns: {
        root: turn("root", null, "root", null, now),
        down: turn("down", "root", "continue", "bottom", now),
        right: turn("right", "down", "fork", "right", now),
        left: turn("left", "down", "fork", "left", now),
      },
      branches: {
        main: {
          branch_id: "main",
          parent_branch_id: null,
          forked_from_turn_id: null,
          head_turn_id: "down",
          active_summary_id: null,
          created_at: now,
        },
      },
      summaries: {},
      citations: {},
    };

    const positions = layoutConversation(conversation);
    const unique = new Set(
      Object.values(positions).map(
        (position) => `${position.x}:${position.y}`,
      ),
    );

    expect(unique.size).toBe(4);
    expect(positions.down.y).toBeGreaterThan(positions.root.y);
    expect(positions.right.x).toBeGreaterThan(positions.down.x);
    expect(positions.left.x).toBeLessThan(positions.down.x);
  });
});

function turn(
  turnId: string,
  parentTurnId: string | null,
  connectionKind: "root" | "continue" | "fork",
  parentPort: "top" | "right" | "bottom" | "left" | null,
  createdAt: string,
) {
  return {
    turn_id: turnId,
    parent_turn_id: parentTurnId,
    connection_kind: connectionKind,
    parent_port: parentPort,
    user_content: "问题",
    assistant_content: "回答",
    citation_ids: [],
    provider: "openai",
    model: "gpt-5.6",
    created_at: createdAt,
  };
}
