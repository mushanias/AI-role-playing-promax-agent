import { useEffect } from "react";

import { Onboarding } from "../features/setup/ui/Onboarding";
import { ConnectionPanel } from "../features/setup/ui/ConnectionPanel";
import { Workspace } from "../features/workspace/ui/Workspace";
import { useAppStore } from "./useAppStore";

export function App() {
  const initialized = useAppStore((state) => state.initialized);
  const initialize = useAppStore((state) => state.initialize);
  const connection = useAppStore((state) => state.connection);
  const activeGoal = useAppStore((state) => state.activeGoal);
  const error = useAppStore((state) => state.error);
  const notice = useAppStore((state) => state.notice);
  const clearFeedback = useAppStore(
    (state) => state.clearFeedback,
  );

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!error && !notice) {
      return;
    }
    const timer = window.setTimeout(clearFeedback, 6000);
    return () => window.clearTimeout(timer);
  }, [error, notice, clearFeedback]);

  if (!initialized) {
    return (
      <div className="loading-screen">
        <div className="brand-mark">L</div>
        <p>正在打开你的学习路径…</p>
      </div>
    );
  }

  return (
    <>
      {activeGoal ? <Workspace /> : <Onboarding />}
      {!connection && activeGoal && (
        <div className="modal-backdrop reconnect">
          <section className="dialog connection-dialog">
            <ConnectionPanel
              compact
              title={`重新连接 ${activeGoal.runtime_model.model}`}
            />
          </section>
        </div>
      )}
      {(error || notice) && (
        <button
          className={`toast ${error ? "error" : "notice"}`}
          onClick={clearFeedback}
        >
          <span>{error ? "!" : "✓"}</span>
          {error ?? notice}
        </button>
      )}
    </>
  );
}
