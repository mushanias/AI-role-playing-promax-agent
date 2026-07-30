import { useCallback, useState } from "react";

import { useAppStore } from "../../../app/useAppStore";
import type { LearningTurn } from "../../../shared/contracts/learning";
import { Composer } from "../../chat/ui/Composer";
import { HistoryPanel } from "../../history/ui/HistoryPanel";
import { ConversationMap } from "../../map/ui/ConversationMap";
import { GoalForm } from "../../setup/ui/GoalForm";

export function Workspace() {
  const goal = useAppStore((state) => state.activeGoal)!;
  const goals = useAppStore((state) => state.goals);
  const selectGoal = useAppStore((state) => state.selectGoal);
  const openGoalEditor = useAppStore(
    (state) => state.openGoalEditor,
  );
  const closeGoalEditor = useAppStore(
    (state) => state.closeGoalEditor,
  );
  const goalEditorOpen = useAppStore(
    (state) => state.goalEditorOpen,
  );
  const disconnect = useAppStore((state) => state.disconnect);
  const exportData = useAppStore((state) => state.exportData);
  const importData = useAppStore((state) => state.importData);
  const [fullTurn, setFullTurn] = useState<LearningTurn | null>(
    null,
  );

  const viewFull = useCallback(
    (turnId: string) => {
      setFullTurn(goal.local_state.conversation.turns[turnId]);
    },
    [goal],
  );

  function downloadBackup() {
    const blob = new Blob([exportData()], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `learning-agent-${new Date()
      .toISOString()
      .slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function uploadBackup(
    event: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await importData(await file.text());
    event.target.value = "";
  }

  return (
    <div className="workspace">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark small">L</div>
          <div>
            <strong>学习路径</strong>
            <span>每个问题都有来路</span>
          </div>
        </div>
        <div className="goal-switcher">
          <span>学习目标</span>
          <select
            value={goal.goal_id}
            onChange={(event) => selectGoal(event.target.value)}
          >
            {goals.map((item) => (
              <option key={item.goal_id} value={item.goal_id}>
                {item.name}
              </option>
            ))}
          </select>
          <button className="icon-button" onClick={openGoalEditor}>
            ＋ 新目标
          </button>
        </div>
        <nav className="top-actions">
          <button onClick={downloadBackup}>导出</button>
          <label className="import-button">
            导入
            <input
              type="file"
              accept="application/json"
              onChange={uploadBackup}
            />
          </label>
          <button onClick={disconnect}>清除 Key</button>
        </nav>
      </header>

      <main className="workspace-main">
        <section className="map-column">
          <div className="goal-context">
            <div>
              <span className="eyebrow">当前目标</span>
              <h1>{goal.name}</h1>
            </div>
            <div className="goal-pills">
              <span>{goal.runtime_model.model}</span>
              <span>{goal.prompt_snapshot.name}</span>
              <span>
                {Object.keys(goal.local_state.conversation.turns).length}{" "}
                个节点
              </span>
            </div>
          </div>
          {goal.local_state.conversation.root_turn_id ? (
            <ConversationMap
              conversation={goal.local_state.conversation}
              onViewFull={viewFull}
            />
          ) : (
            <div className="empty-map">
              <i className="spinner dark" />
              <h2>正在生成第一份学习规划</h2>
              <p>如果刚才连接中断，可以直接在下方输入框重试。</p>
            </div>
          )}
          <Composer />
        </section>
        <HistoryPanel />
      </main>

      {fullTurn && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={() => setFullTurn(null)}
        >
          <section
            className="dialog full-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="完整对话"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <div className="eyebrow">完整对话</div>
                <h2>这一节点的一问一答</h2>
              </div>
              <button
                className="close-button"
                onClick={() => setFullTurn(null)}
              >
                ×
              </button>
            </header>
            <div className="full-message user">
              <strong>你的提问</strong>
              <p>{fullTurn.user_content}</p>
            </div>
            <div className="full-message assistant">
              <strong>AI 的回答</strong>
              <p>{fullTurn.assistant_content}</p>
            </div>
            {fullTurn.citation_ids.length > 0 && (
              <div className="citation-list">
                <strong>参考来源</strong>
                {fullTurn.citation_ids.map((citationId) => {
                  const citation =
                    goal.local_state.conversation.citations[
                      citationId
                    ];
                  return citation?.url ? (
                    <a
                      key={citationId}
                      href={citation.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {citation.title} ↗
                    </a>
                  ) : (
                    <span key={citationId}>
                      {citation?.title ?? citationId}
                    </span>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}

      {goalEditorOpen && (
        <div className="modal-backdrop">
          <section className="dialog goal-dialog">
            <GoalForm onCancel={closeGoalEditor} />
          </section>
        </div>
      )}
    </div>
  );
}
