"""一次性测试前端：启动现有 FastAPI 后端，并在 /ui 提供单文件界面。"""

import uvicorn
from fastapi.responses import HTMLResponse

from app.main import app


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>版本化会话引擎测试界面</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #111827;
      color: #e5e7eb;
    }
    button, textarea { font: inherit; }
    button {
      border: 1px solid #4b5563;
      border-radius: 7px;
      padding: 7px 11px;
      background: #1f2937;
      color: #f9fafb;
      cursor: pointer;
    }
    button:hover { background: #374151; }
    button:disabled { opacity: .45; cursor: not-allowed; }
    .app {
      width: min(920px, 100%);
      min-height: 100vh;
      margin: auto;
      display: grid;
      grid-template-rows: auto 1fr auto;
      background: #0f172a;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid #334155;
      background: #0f172a;
    }
    .identity {
      min-width: 0;
      flex: 1;
      color: #94a3b8;
      font-size: 13px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    #messages {
      padding: 18px 14px 130px;
      overflow-y: auto;
    }
    .empty {
      margin: 80px auto;
      max-width: 520px;
      color: #94a3b8;
      line-height: 1.8;
      text-align: center;
    }
    .turn {
      margin: 0 0 22px;
    }
    .bubble {
      max-width: 82%;
      padding: 12px 14px;
      border-radius: 12px;
      line-height: 1.65;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .user {
      margin-left: auto;
      background: #1d4ed8;
      color: white;
    }
    .assistant {
      margin-top: 10px;
      margin-right: auto;
      background: #1f2937;
    }
    .pending { opacity: .65; }
    .controls {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 5px;
      min-height: 32px;
      margin-top: 5px;
      color: #94a3b8;
      font-size: 12px;
    }
    .controls button {
      padding: 3px 7px;
      border: 0;
      background: transparent;
      color: #cbd5e1;
    }
    .composer {
      position: fixed;
      left: 50%;
      bottom: 0;
      width: min(920px, 100%);
      transform: translateX(-50%);
      padding: 12px;
      border-top: 1px solid #334155;
      background: #0f172a;
    }
    form { display: flex; gap: 8px; align-items: flex-end; }
    textarea {
      flex: 1;
      min-height: 54px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid #475569;
      border-radius: 9px;
      padding: 10px;
      background: #111827;
      color: #f8fafc;
    }
    .status {
      min-height: 20px;
      margin-top: 7px;
      color: #94a3b8;
      font-size: 13px;
    }
    .status.error { color: #fca5a5; }
    .status.warning { color: #fcd34d; }
    @media (max-width: 600px) {
      .bubble { max-width: 94%; }
      header button { padding: 6px 8px; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header>
      <button id="newConversation">新建会话</button>
      <button id="reloadHistory">刷新历史</button>
      <span class="identity" id="identity">尚未创建会话</span>
    </header>

    <section id="messages">
      <div class="empty">点击“新建会话”，然后开始测试发送、修改和左右切换。</div>
    </section>

    <section class="composer">
      <form id="sendForm">
        <textarea id="messageInput" placeholder="输入消息；Enter 发送，Shift+Enter 换行"></textarea>
        <button id="sendButton" type="submit">发送</button>
      </form>
      <div class="status" id="status"></div>
    </section>
  </main>

  <script>
    const state = {
      conversationId: localStorage.getItem("testConversationId"),
      branchId: null,
      busy: false,
    };

    const messages = document.querySelector("#messages");
    const identity = document.querySelector("#identity");
    const status = document.querySelector("#status");
    const input = document.querySelector("#messageInput");
    const sendButton = document.querySelector("#sendButton");
    const newButton = document.querySelector("#newConversation");
    const reloadButton = document.querySelector("#reloadHistory");

    function setBusy(value, text = "") {
      state.busy = value;
      sendButton.disabled = value;
      newButton.disabled = value;
      reloadButton.disabled = value || !state.conversationId;
      input.disabled = value;
      if (text) setStatus(text);
    }

    function setStatus(text = "", kind = "") {
      status.textContent = text;
      status.className = `status ${kind}`;
    }

    function updateIdentity() {
      if (!state.conversationId) {
        identity.textContent = "尚未创建会话";
        return;
      }
      identity.textContent = `会话 ${state.conversationId} ｜ 分支 ${state.branchId || "加载中"}`;
    }

    async function request(path, options = {}) {
      const response = await fetch(path, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
      });
      let data = null;
      try {
        data = await response.json();
      } catch (_) {
        data = null;
      }
      if (!response.ok) {
        const detail = data?.error?.message || data?.detail || `HTTP ${response.status}`;
        throw new Error(detail);
      }
      return data;
    }

    async function createConversation() {
      if (state.busy) return;
      setBusy(true, "正在创建会话……");
      try {
        const data = await request("/conversations", { method: "POST" });
        state.conversationId = data.conversation_id;
        state.branchId = data.active_branch_id;
        localStorage.setItem("testConversationId", state.conversationId);
        updateIdentity();
        renderTurns([]);
        setStatus("新会话已创建");
        input.focus();
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        setBusy(false);
      }
    }

    async function loadHistory(options = {}) {
      if (!state.conversationId || state.busy) return;
      const quiet = options.quiet === true;
      setBusy(true, quiet ? "" : "正在读取历史……");
      try {
        const data = await request(
          `/conversations/${encodeURIComponent(state.conversationId)}/history`
        );
        state.branchId = data.branch_id;
        updateIdentity();
        renderTurns(data.turns);
        if (!quiet) setStatus(`已加载 ${data.turns.length} 个轮次`);
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        setBusy(false);
      }
    }

    function renderTurns(turns) {
      messages.replaceChildren();
      if (!turns.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "当前分支还没有对话。";
        messages.append(empty);
        return;
      }

      for (const turn of turns) {
        const article = document.createElement("article");
        article.className = "turn";

        const user = document.createElement("div");
        user.className = `bubble user ${turn.status === "pending" ? "pending" : ""}`;
        user.textContent = turn.user_content;
        article.append(user);

        const controls = document.createElement("div");
        controls.className = "controls";

        if (turn.status === "completed") {
          const edit = document.createElement("button");
          edit.type = "button";
          edit.textContent = "修改";
          edit.addEventListener("click", () => rewriteTurn(turn));
          controls.append(edit);
        }

        if (turn.has_variants) {
          const previous = document.createElement("button");
          previous.type = "button";
          previous.textContent = "←";
          previous.disabled = turn.variant_index <= 0;
          previous.addEventListener("click", () => switchVariant(turn, -1));

          const position = document.createElement("span");
          position.textContent = `${turn.variant_index + 1} / ${turn.variant_count}`;

          const next = document.createElement("button");
          next.type = "button";
          next.textContent = "→";
          next.disabled = turn.variant_index >= turn.variant_count - 1;
          next.addEventListener("click", () => switchVariant(turn, 1));

          controls.append(previous, position, next);
        }
        article.append(controls);

        if (turn.assistant_content !== null) {
          const assistant = document.createElement("div");
          assistant.className = "bubble assistant";
          assistant.textContent = turn.assistant_content;
          article.append(assistant);
        } else if (turn.status === "pending") {
          const assistant = document.createElement("div");
          assistant.className = "bubble assistant pending";
          assistant.textContent = "正在生成……";
          article.append(assistant);
        }

        messages.append(article);
      }
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    }

    async function sendMessage(text) {
      if (!state.conversationId) {
        await createConversation();
        if (!state.conversationId) return;
      }
      setBusy(true, "正在生成回复……");
      try {
        const result = await request(
          `/conversations/${encodeURIComponent(state.conversationId)}/turns`,
          {
            method: "POST",
            body: JSON.stringify({ message: text, branch_id: state.branchId }),
          }
        );
        state.branchId = result.branch_id;
        input.value = "";
        await refreshWhileBusy();
        showWarnings(result.warnings);
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        setBusy(false);
        input.focus();
      }
    }

    async function rewriteTurn(turn) {
      if (state.busy) return;
      const replacement = window.prompt("修改这条用户消息：", turn.user_content);
      if (replacement === null || replacement.length === 0 || replacement === turn.user_content) return;

      setBusy(true, "正在从该轮创建新会话分支……");
      try {
        const result = await request(
          `/conversations/${encodeURIComponent(state.conversationId)}/turns/${encodeURIComponent(turn.turn_id)}/rewrite`,
          {
            method: "POST",
            body: JSON.stringify({
              message: replacement,
              source_branch_id: state.branchId,
            }),
          }
        );
        state.branchId = result.branch_id;
        await refreshWhileBusy();
        showWarnings(result.warnings);
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        setBusy(false);
      }
    }

    async function switchVariant(turn, offset) {
      if (state.busy) return;
      setBusy(true, "正在切换消息版本……");
      try {
        const data = await request(
          `/conversations/${encodeURIComponent(state.conversationId)}/turns/${encodeURIComponent(turn.turn_id)}/variants`
        );
        const targetIndex = turn.variant_index + offset;
        const target = data.variants[targetIndex];
        if (!target) throw new Error("目标消息版本不存在");

        await request(
          `/conversations/${encodeURIComponent(state.conversationId)}/branches/${encodeURIComponent(target.branch_id)}/activate`,
          { method: "POST" }
        );
        state.branchId = target.branch_id;
        await refreshWhileBusy();
        setStatus(`已切换到版本 ${targetIndex + 1} / ${data.variants.length}`);
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        setBusy(false);
      }
    }

    async function refreshWhileBusy() {
      const data = await request(
        `/conversations/${encodeURIComponent(state.conversationId)}/history`
      );
      state.branchId = data.branch_id;
      updateIdentity();
      renderTurns(data.turns);
    }

    function showWarnings(warnings = []) {
      if (warnings.length) {
        setStatus(warnings.join(" ｜ "), "warning");
      } else {
        setStatus("完成");
      }
    }

    document.querySelector("#newConversation").addEventListener("click", createConversation);
    document.querySelector("#reloadHistory").addEventListener("click", () => loadHistory());
    document.querySelector("#sendForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = input.value;
      if (!text.length || state.busy) return;
      await sendMessage(text);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        document.querySelector("#sendForm").requestSubmit();
      }
    });

    updateIdentity();
    reloadButton.disabled = !state.conversationId;
    if (state.conversationId) loadHistory();
  </script>
</body>
</html>
"""


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def test_ui() -> HTMLResponse:
    """返回一次性单文件测试界面。"""
    return HTMLResponse(HTML)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
