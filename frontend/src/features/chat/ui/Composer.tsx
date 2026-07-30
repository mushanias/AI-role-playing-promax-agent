import { useMemo, useState } from "react";

import { useAppStore } from "../../../app/useAppStore";
import type {
  NodePort,
  RetrievalMode,
} from "../../../shared/contracts/learning";
import { occupiedChildPorts } from "../application/graphSelectors";

export function Composer() {
  const goal = useAppStore((state) => state.activeGoal);
  const currentTurnId = useAppStore(
    (state) => state.currentTurnId,
  );
  const forceFork = useAppStore((state) => state.forceFork);
  const setForceFork = useAppStore((state) => state.setForceFork);
  const busy = useAppStore((state) => state.busy);
  const sendTurn = useAppStore((state) => state.sendTurn);
  const [text, setText] = useState("");
  const [retrievalMode, setRetrievalMode] =
    useState<RetrievalMode>("auto");

  const branchState = useMemo(() => {
    if (!goal || !currentTurnId) {
      return { allowed: false, reason: "还没有节点" };
    }
    const conversation = goal.local_state.conversation;
    const turn = conversation.turns[currentTurnId];
    if (!turn || turn.connection_kind === "root") {
      return { allowed: false, reason: "根节点不能创建分支" };
    }
    const incoming = turn.parent_port!;
    const perpendicular =
      incoming === "top" || incoming === "bottom"
        ? ["left", "right"]
        : ["top", "bottom"];
    const occupied = occupiedChildPorts(conversation, currentTurnId);
    const available = perpendicular.filter(
      (port) => !occupied.has(port as NodePort),
    );
    return {
      allowed: available.length > 0,
      reason:
        available.length > 0
          ? `还有 ${available.length} 个转弯方向`
          : "这个节点的分支方向已经用满",
    };
  }, [goal, currentTurnId]);

  const currentIsHead = useMemo(() => {
    if (!goal || !currentTurnId) {
      return true;
    }
    return Object.values(
      goal.local_state.conversation.branches,
    ).some((branch) => branch.head_turn_id === currentTurnId);
  }, [goal, currentTurnId]);
  const willFork = forceFork || !currentIsHead;

  async function submit() {
    if (!text.trim() || busy) {
      return;
    }
    const sent = text;
    setText("");
    await sendTurn(sent, retrievalMode);
  }

  return (
    <div className="composer-wrap">
      <div className="composer-status">
        <button
          className={`branch-toggle ${forceFork ? "active" : ""}`}
          disabled={!branchState.allowed || busy}
          title={branchState.reason}
          onClick={() => setForceFork(!forceFork)}
        >
          ↪ {forceFork ? "分支模式已开启" : "从这里创建分支"}
        </button>
        {willFork && currentTurnId && (
          <span className="fork-notice">
            下一条问答会转弯进入独立分支
          </span>
        )}
        <select
          aria-label="资料来源"
          value={retrievalMode}
          onChange={(event) =>
            setRetrievalMode(event.target.value as RetrievalMode)
          }
        >
          <option value="auto">资料：自动</option>
          <option value="knowledge_base_only">仅公共知识库</option>
          <option value="web_only">仅联网</option>
          <option value="knowledge_base_and_web">
            知识库 + 联网
          </option>
        </select>
      </div>
      <div className="composer">
        <textarea
          value={text}
          disabled={busy}
          placeholder={
            forceFork
              ? "这个问题会开启一条独立分支…"
              : "继续当前学习路径…"
          }
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button
          className="send-button"
          disabled={!text.trim() || busy}
          onClick={submit}
          aria-label="发送"
        >
          {busy ? <i className="spinner" /> : "↑"}
        </button>
      </div>
      <p className="composer-help">
        Enter 发送，Shift + Enter 换行。服务端成功返回后才会写入本地。
      </p>
    </div>
  );
}
