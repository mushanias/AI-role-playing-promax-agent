import { useAppStore } from "../../../app/useAppStore";
import { ConnectionPanel } from "./ConnectionPanel";
import { GoalForm } from "./GoalForm";

export function Onboarding() {
  const connection = useAppStore((state) => state.connection);
  const goals = useAppStore((state) => state.goals);

  return (
    <div className="onboarding-shell">
      <aside className="onboarding-story">
        <div className="brand-mark">L</div>
        <div>
          <div className="eyebrow light">学习路径 Agent</div>
          <h2>问题可以岔开，进度不会丢失。</h2>
          <p>
            每一问一答都是一个节点。主线向下，追问转弯；任何时候都能回到当时的理解位置。
          </p>
        </div>
        <div className="story-map" aria-hidden="true">
          <i className="dot d1" />
          <i className="dot d2" />
          <i className="dot d3 active" />
          <i className="dot d4" />
          <i className="line l1" />
          <i className="line l2" />
          <i className="line l3" />
        </div>
        <p className="privacy-note">
          会话默认只在当前浏览器保存。换设备前，请先导出学习数据。
        </p>
      </aside>
      <main className="onboarding-main">
        {!connection ? (
          <ConnectionPanel
            title={
              goals.length
                ? "重新连接这个目标使用的模型"
                : "先连接你自己的模型"
            }
          />
        ) : (
          <GoalForm />
        )}
      </main>
    </div>
  );
}
