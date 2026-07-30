import { createServer } from "node:http";

const presets = {
  default_provider: "openai",
  default_model: "gpt-5.6",
  providers: [
    {
      id: "openai",
      name: "GPT / OpenAI",
      models: ["gpt-5.6"],
      default_model: "gpt-5.6",
      docs_url: "https://developers.openai.com/",
      supports_native_search: true,
      context_window: 128000,
    },
  ],
};

const server = createServer(async (request, response) => {
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  if (request.method === "GET" && request.url === "/llm/presets") {
    return send(response, 200, presets);
  }
  if (
    request.method === "POST" &&
    request.url === "/llm/connection-test"
  ) {
    return send(response, 200, {
      success: true,
      message: "连接成功",
    });
  }
  if (
    request.method === "POST" &&
    request.url === "/learning/conversations/turns"
  ) {
    const command = JSON.parse(await readBody(request));
    return send(response, 200, buildDelta(command));
  }
  return send(response, 404, {
    error: { code: "not_found", message: "测试路由不存在" },
  });
});

server.listen(8000, "127.0.0.1", () => {
  console.log("前端交互测试 API 已启动：http://127.0.0.1:8000");
});

function buildDelta(command) {
  const now = new Date().toISOString();
  const source = command.compact_graph.turns.find(
    (turn) => turn.turn_id === command.source_turn_id,
  );
  const parentPort =
    command.action === "create_root"
      ? null
      : command.action === "append_turn"
        ? source?.connection_kind === "root"
          ? "bottom"
          : source?.parent_port
        : chooseForkPort(command, source);
  const connectionKind =
    command.action === "create_root"
      ? "root"
      : command.action === "append_turn"
        ? "continue"
        : "fork";
  const answer =
    command.action === "create_root"
      ? "我建议把目标拆成四步：\n\n1. 建立核心概念框架\n2. 用例子理解关键关系\n3. 通过练习检查薄弱点\n4. 综合应用并复盘\n\n如果你确认，我们从第一点开始。"
      : `这是“${command.user_text}”对应的学习回答。这个节点已经保存到当前路径，并且不会影响其他分支。`;
  const citationId = `${command.new_turn_id}-web-test`;
  const turn = {
    turn_id: command.new_turn_id,
    parent_turn_id: command.source_turn_id,
    connection_kind: connectionKind,
    parent_port: parentPort,
    user_content: command.user_text,
    assistant_content: answer,
    citation_ids: [citationId],
    provider: command.runtime_model.provider,
    model: command.runtime_model.model,
    created_at: now,
  };
  const isFork = command.action === "fork_from_turn";
  const branchId = isFork
    ? command.new_branch_id
    : command.action === "create_root"
      ? command.compact_graph.main_branch_id
      : command.active_branch_id;
  return {
    operation_id: command.operation_id,
    old_revision: command.expected_revision,
    new_revision: command.expected_revision + 1,
    added_turns: [turn],
    added_branches: isFork
      ? [
          {
            branch_id: command.new_branch_id,
            parent_branch_id: command.active_branch_id,
            forked_from_turn_id: command.source_turn_id,
            head_turn_id: command.new_turn_id,
            active_summary_id: null,
            created_at: now,
          },
        ]
      : [],
    added_summaries: [],
    added_citations: [
      {
        citation_id: citationId,
        turn_id: command.new_turn_id,
        source: "web",
        title: "交互测试来源",
        url: "https://example.com/source",
        publisher: "本地测试",
        published_at: null,
        retrieved_at: now,
        knowledge_base_version: null,
        reference_id: null,
      },
    ],
    branch_head_updates: isFork
      ? []
      : [
          {
            branch_id: branchId,
            old_head_turn_id: command.source_turn_id,
            new_head_turn_id: command.new_turn_id,
            new_active_summary_id: null,
          },
        ],
    next_active_branch_id: branchId,
    next_active_head_turn_id: command.new_turn_id,
    warnings: [],
    usage: { input_tokens: 100, output_tokens: 50 },
  };
}

function chooseForkPort(command, source) {
  if (command.preferred_port) {
    return command.preferred_port;
  }
  const perpendicular =
    source.parent_port === "top" || source.parent_port === "bottom"
      ? ["right", "left"]
      : ["bottom", "top"];
  const occupied = new Set(
    command.compact_graph.turns
      .filter((turn) => turn.parent_turn_id === source.turn_id)
      .map((turn) => turn.parent_port),
  );
  return perpendicular.find((port) => !occupied.has(port));
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => resolve(body));
    request.on("error", reject);
  });
}

function send(response, status, payload) {
  response.statusCode = status;
  response.end(JSON.stringify(payload));
}
