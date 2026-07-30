import type { LearningConversation } from "../../../shared/contracts/learning";
import { findSourceBranch, turnPath } from "./graphSelectors";

describe("图路径选择", () => {
  it("公共祖先正好是某条分支末端时优先选择该分支", () => {
    const now = new Date().toISOString();
    const conversation: LearningConversation = {
      schema_version: 1,
      conversation_id: "conversation",
      revision: 3,
      main_branch_id: "main",
      root_turn_id: "root",
      turns: {
        root: turn("root", null, "root", null, now),
        mainHead: turn(
          "mainHead",
          "root",
          "continue",
          "bottom",
          now,
        ),
        forkHead: turn(
          "forkHead",
          "mainHead",
          "fork",
          "right",
          now,
        ),
      },
      branches: {
        main: {
          branch_id: "main",
          parent_branch_id: null,
          forked_from_turn_id: null,
          head_turn_id: "mainHead",
          active_summary_id: null,
          created_at: now,
        },
        fork: {
          branch_id: "fork",
          parent_branch_id: "main",
          forked_from_turn_id: "mainHead",
          head_turn_id: "forkHead",
          active_summary_id: null,
          created_at: now,
        },
      },
      summaries: {},
      citations: {},
    };

    const selected = findSourceBranch(
      conversation,
      "mainHead",
      "fork",
    );

    expect(selected.branch_id).toBe("main");
    expect(
      turnPath(conversation, "forkHead").map((item) => item.turn_id),
    ).toEqual(["root", "mainHead", "forkHead"]);
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
