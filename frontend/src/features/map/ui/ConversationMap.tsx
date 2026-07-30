import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type NodeMouseHandler,
  type Viewport,
} from "@xyflow/react";
import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useAppStore } from "../../../app/useAppStore";
import type {
  LearningConversation,
  NodePort,
} from "../../../shared/contracts/learning";
import { layoutConversation } from "../application/graphLayout";
import {
  TurnNode,
  type TurnFlowNode,
} from "./TurnNode";

import "@xyflow/react/dist/style.css";

const nodeTypes = { turn: TurnNode };
const opposite: Record<NodePort, NodePort> = {
  top: "bottom",
  right: "left",
  bottom: "top",
  left: "right",
};

interface ConversationMapProps {
  conversation: LearningConversation;
  onViewFull: (turnId: string) => void;
}

export function ConversationMap({
  conversation,
  onViewFull,
}: ConversationMapProps) {
  const focusedTurnId = useAppStore(
    (state) => state.focusedTurnId,
  );
  const currentTurnId = useAppStore(
    (state) => state.currentTurnId,
  );
  const focusTurn = useAppStore((state) => state.focusTurn);
  const activateTurn = useAppStore((state) => state.activateTurn);
  const [viewport, setViewport] = useState<Viewport>({
    x: 0,
    y: 0,
    zoom: 0.85,
  });
  const moveStart = useRef<Viewport>(viewport);
  const axis = useRef<"x" | "y" | null>(null);
  const mapElement = useRef<HTMLDivElement | null>(null);

  const { nodes, edges } = useMemo(
    () =>
      toFlowElements(
        conversation,
        currentTurnId,
        focusedTurnId,
        onViewFull,
        activateTurn,
      ),
    [
      conversation,
      currentTurnId,
      focusedTurnId,
      onViewFull,
      activateTurn,
    ],
  );

  const onNodeClick: NodeMouseHandler<TurnFlowNode> = useCallback(
    (_, node) => focusTurn(node.id),
    [focusTurn],
  );
  const currentNode = nodes.find((node) => node.id === currentTurnId);

  useLayoutEffect(() => {
    if (!currentNode || !mapElement.current) {
      return;
    }
    const zoom = 0.82;
    const width = currentNode.measured?.width ?? 360;
    const height = currentNode.measured?.height ?? 230;
    const nextViewport = {
      x:
        mapElement.current.clientWidth / 2 -
        (currentNode.position.x + width / 2) * zoom,
      y:
        mapElement.current.clientHeight / 2 -
        (currentNode.position.y + height / 2) * zoom,
      zoom,
    };
    moveStart.current = nextViewport;
    axis.current = null;
    setViewport(nextViewport);
  }, [
    currentNode?.id,
    currentNode?.position.x,
    currentNode?.position.y,
  ]);

  function handleMoveStart(_: unknown, next: Viewport) {
    moveStart.current = next;
    axis.current = null;
  }

  function handleMove(_: unknown, next: Viewport) {
    const start = moveStart.current;
    if (next.zoom !== start.zoom) {
      setViewport(next);
      moveStart.current = next;
      return;
    }
    const dx = next.x - start.x;
    const dy = next.y - start.y;
    if (!axis.current && Math.max(Math.abs(dx), Math.abs(dy)) > 5) {
      axis.current = Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
    }
    setViewport({
      x: axis.current === "y" ? start.x : next.x,
      y: axis.current === "x" ? start.y : next.y,
      zoom: next.zoom,
    });
  }

  return (
    <div className="conversation-map" ref={mapElement}>
      <ReactFlow<TurnFlowNode>
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        viewport={viewport}
        onMoveStart={handleMoveStart}
        onMove={handleMove}
        onNodeClick={onNodeClick}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        minZoom={0.35}
        maxZoom={1.35}
        onlyRenderVisibleElements
        defaultEdgeOptions={{
          type: "smoothstep",
          animated: false,
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="rgba(55, 65, 81, .14)"
        />
        <Controls
          position="bottom-left"
          showInteractive={false}
        />
        <MiniMap<TurnFlowNode>
          pannable
          zoomable
          position="top-right"
          nodeColor={(node) =>
            node.id === currentTurnId ? "#ef5b45" : "#d5d0c6"
          }
          nodeStrokeColor={(node) =>
            node.id === currentTurnId ? "#b93025" : "#8a8175"
          }
          nodeStrokeWidth={4}
          maskColor="rgba(246, 242, 234, .75)"
        />
      </ReactFlow>
      <div className="map-hint">
        拖动画布查看 · 单击预览 · 双击切换当前位置
      </div>
    </div>
  );
}

function toFlowElements(
  conversation: LearningConversation,
  currentTurnId: string | null,
  focusedTurnId: string | null,
  onViewFull: (turnId: string) => void,
  onActivate: (turnId: string) => void,
): { nodes: TurnFlowNode[]; edges: Edge[] } {
  const positions = layoutConversation(conversation);
  const nodes: TurnFlowNode[] = Object.values(conversation.turns).map(
    (turn) => {
      const horizontal =
        turn.parent_port === "left" ||
        turn.parent_port === "right";
      return {
        id: turn.turn_id,
        type: "turn",
        position: positions[turn.turn_id] ?? { x: 0, y: 0 },
        measured: {
          width: horizontal ? 410 : 360,
          height: horizontal ? 222 : 230,
        },
        data: {
          turn,
          active: turn.turn_id === currentTurnId,
          focused: turn.turn_id === focusedTurnId,
          onViewFull,
          onActivate,
        },
        zIndex:
          turn.turn_id === currentTurnId
            ? 3
            : turn.turn_id === focusedTurnId
              ? 2
              : 1,
      };
    },
  );
  const edges: Edge[] = Object.values(conversation.turns)
    .filter(
      (
        turn,
      ): turn is typeof turn & {
        parent_turn_id: string;
        parent_port: NodePort;
      } => Boolean(turn.parent_turn_id && turn.parent_port),
    )
    .map((turn) => ({
      id: `${turn.parent_turn_id}-${turn.turn_id}`,
      source: turn.parent_turn_id,
      target: turn.turn_id,
      sourceHandle: `source-${turn.parent_port}`,
      targetHandle: `target-${opposite[turn.parent_port]}`,
      type: "smoothstep",
      style: {
        stroke:
          turn.connection_kind === "fork" ? "#c08755" : "#9b9489",
        strokeWidth: 2,
      },
    }));
  return { nodes, edges };
}
