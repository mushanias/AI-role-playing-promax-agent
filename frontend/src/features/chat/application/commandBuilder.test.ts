import { buildConversationCommand } from "./commandBuilder";
import { createLearningGoal } from "../../goals/application/createGoal";
import { BUILTIN_LEARNING_PROMPTS } from "../../goals/application/prompts";

function emptyGoal() {
  return createLearningGoal({
    name: "测试",
    background: "零基础",
    learningGoal: "学会测试",
    targetLevel: "入门",
    prompt: BUILTIN_LEARNING_PROMPTS[0],
    runtimeModel: { provider: "openai", model: "gpt-5.6" },
  });
}

describe("buildConversationCommand", () => {
  it("空会话创建根节点且不发送历史", () => {
    const goal = emptyGoal();

    const command = buildConversationCommand({
      goal,
      userText: "生成规划",
    });

    expect(command.action).toBe("create_root");
    expect(command.source_turn_id).toBeNull();
    expect(command.active_path_context.recent_turns).toEqual([]);
    expect(command.compact_graph.turns).toEqual([]);
  });

  it("从已有后继的旧节点提问时自动创建独立分支", () => {
    const goal = emptyGoal();
    const conversation = goal.local_state.conversation;
    const branch = conversation.branches[conversation.main_branch_id];
    const rootId = crypto.randomUUID();
    const secondId = crypto.randomUUID();
    conversation.root_turn_id = rootId;
    conversation.revision = 2;
    conversation.turns[rootId] = {
      turn_id: rootId,
      parent_turn_id: null,
      connection_kind: "root",
      parent_port: null,
      user_content: "问题一",
      assistant_content: "回答一",
      citation_ids: [],
      provider: "openai",
      model: "gpt-5.6",
      created_at: new Date().toISOString(),
    };
    conversation.turns[secondId] = {
      turn_id: secondId,
      parent_turn_id: rootId,
      connection_kind: "continue",
      parent_port: "bottom",
      user_content: "问题二",
      assistant_content: "回答二",
      citation_ids: [],
      provider: "openai",
      model: "gpt-5.6",
      created_at: new Date().toISOString(),
    };
    branch.head_turn_id = secondId;
    goal.local_state.active_head_turn_id = secondId;

    const command = buildConversationCommand({
      goal,
      userText: "换个方向追问",
      sourceTurnId: rootId,
    });

    expect(command.action).toBe("fork_from_turn");
    expect(command.new_branch_id).not.toBeNull();
    expect(
      command.active_path_context.recent_turns.map(
        (turn) => turn.turn_id,
      ),
    ).toEqual([rootId]);
  });
});
