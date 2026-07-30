import { useMemo, useState } from "react";

import { useAppStore } from "../../../app/useAppStore";
import { turnPath } from "../../chat/application/graphSelectors";

export function HistoryPanel() {
  const goal = useAppStore((state) => state.activeGoal);
  const focusedTurnId = useAppStore(
    (state) => state.focusedTurnId,
  );
  const [expanded, setExpanded] = useState(false);
  const path = useMemo(() => {
    if (!goal || !focusedTurnId) {
      return [];
    }
    return turnPath(goal.local_state.conversation, focusedTurnId);
  }, [goal, focusedTurnId]);

  return (
    <aside className="history-panel">
      <header>
        <div>
          <div className="eyebrow">当前路径</div>
          <h2>追根溯源</h2>
        </div>
        <button
          className="text-button"
          disabled={!path.length}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "只看提问" : "展开问答"}
        </button>
      </header>
      {!path.length ? (
        <div className="empty-history">
          点击一个节点，这里会显示从起点到它的完整路径。
        </div>
      ) : (
        <ol className="history-list">
          {path.map((turn, index) => (
            <li key={turn.turn_id}>
              <span className="history-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="history-question">{turn.user_content}</p>
                {expanded && (
                  <p className="history-answer">
                    {turn.assistant_content}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
