import {
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type { LearningTurn } from "../../../shared/contracts/learning";

export type TurnNodeData = {
  turn: LearningTurn;
  active: boolean;
  focused: boolean;
  onViewFull: (turnId: string) => void;
  onActivate: (turnId: string) => void;
};

export type TurnFlowNode = Node<TurnNodeData, "turn">;

const handles = [
  ["top", Position.Top],
  ["right", Position.Right],
  ["bottom", Position.Bottom],
  ["left", Position.Left],
] as const;

export function TurnNode({ data }: NodeProps<TurnFlowNode>) {
  const orientation =
    data.turn.parent_port === "left" ||
    data.turn.parent_port === "right"
      ? "horizontal"
      : "vertical";
  return (
    <article
      className={[
        "turn-node",
        orientation,
        data.active ? "active" : "",
        data.focused ? "focused" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onDoubleClick={(event) => {
        event.stopPropagation();
        data.onActivate(data.turn.turn_id);
      }}
      onClick={(event) => {
        if (event.detail < 2) {
          return;
        }
        event.stopPropagation();
        data.onActivate(data.turn.turn_id);
      }}
    >
      {handles.map(([name, position]) => (
        <span key={name}>
          <Handle
            type="source"
            id={`source-${name}`}
            position={position}
            className="turn-handle"
          />
          <Handle
            type="target"
            id={`target-${name}`}
            position={position}
            className="turn-handle"
          />
        </span>
      ))}
      <header>
        <span className="turn-index">
          {new Date(data.turn.created_at).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        {data.active && <span className="current-badge">当前位置</span>}
      </header>
      <div className="message user-message">
        <span>你</span>
        <p>{data.turn.user_content}</p>
      </div>
      <div className="message assistant-message">
        <span>AI</span>
        <p>{data.turn.assistant_content}</p>
      </div>
      <button
        className="view-full"
        onClick={(event) => {
          event.stopPropagation();
          data.onViewFull(data.turn.turn_id);
        }}
      >
        查看完整对话
      </button>
    </article>
  );
}
