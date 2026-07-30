import { create } from "zustand";

import { buildConversationCommand } from "../features/chat/application/commandBuilder";
import { findSourceBranch } from "../features/chat/application/graphSelectors";
import { createLearningGoal } from "../features/goals/application/createGoal";
import type {
  GoalDraft,
  LearningGoal,
} from "../features/goals/domain/models";
import {
  parseBackup,
  serializeBackup,
} from "../features/goals/storage/backup";
import type { RetrievalMode } from "../shared/contracts/learning";
import type { LLMPresetList } from "../shared/contracts/llm";
import { goalRepository, learningApiClient } from "./services";

interface ConnectionState {
  apiKey: string;
  provider: string;
  model: string;
}

interface AppState {
  initialized: boolean;
  presets: LLMPresetList | null;
  goals: LearningGoal[];
  activeGoal: LearningGoal | null;
  connection: ConnectionState | null;
  focusedTurnId: string | null;
  currentTurnId: string | null;
  focusedBranchId: string | null;
  forceFork: boolean;
  busy: boolean;
  connectionBusy: boolean;
  error: string | null;
  notice: string | null;
  goalEditorOpen: boolean;
  initialize: () => Promise<void>;
  retryPresets: () => Promise<void>;
  connect: (input: ConnectionState) => Promise<boolean>;
  disconnect: () => void;
  createGoalAndStart: (draft: GoalDraft) => Promise<void>;
  selectGoal: (goalId: string) => Promise<void>;
  focusTurn: (turnId: string) => void;
  activateTurn: (turnId: string) => void;
  setForceFork: (enabled: boolean) => void;
  sendTurn: (
    userText: string,
    retrievalMode: RetrievalMode,
  ) => Promise<void>;
  openGoalEditor: () => void;
  closeGoalEditor: () => void;
  exportData: () => string;
  importData: (raw: string) => Promise<void>;
  clearFeedback: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  initialized: false,
  presets: null,
  goals: [],
  activeGoal: null,
  connection: null,
  focusedTurnId: null,
  currentTurnId: null,
  focusedBranchId: null,
  forceFork: false,
  busy: false,
  connectionBusy: false,
  error: null,
  notice: null,
  goalEditorOpen: false,

  initialize: async () => {
    try {
      const [goals, presets] = await Promise.all([
        goalRepository.list(),
        learningApiClient.listModelPresets(),
      ]);
      const savedGoalId = await goalRepository.getActiveGoalId();
      const activeGoal =
        goals.find((goal) => goal.goal_id === savedGoalId) ??
        goals[0] ??
        null;
      set({
        initialized: true,
        goals,
        presets,
        activeGoal,
        focusedTurnId:
          activeGoal?.local_state.active_head_turn_id ?? null,
        currentTurnId:
          activeGoal?.local_state.active_head_turn_id ?? null,
        focusedBranchId:
          activeGoal?.local_state.active_branch_id ?? null,
      });
    } catch (error) {
      const goals = await goalRepository.list();
      const activeGoal = goals[0] ?? null;
      set({
        initialized: true,
        goals,
        activeGoal,
        error: messageOf(
          error,
          "无法连接后端，请确认后端服务已经启动",
        ),
      });
    }
  },

  retryPresets: async () => {
    try {
      const presets = await learningApiClient.listModelPresets();
      set({ presets, error: null });
    } catch (error) {
      set({ error: messageOf(error, "仍然无法连接后端") });
    }
  },

  connect: async (input) => {
    set({ connectionBusy: true, error: null });
    try {
      const result = await learningApiClient.testConnection({
        apiKey: input.apiKey,
        provider: input.provider,
        model: input.model,
      });
      if (!result.success) {
        set({ error: result.message, connectionBusy: false });
        return false;
      }
      set({
        connection: input,
        connectionBusy: false,
        notice: "连接成功",
      });
      return true;
    } catch (error) {
      set({
        connectionBusy: false,
        error: messageOf(error, "连接失败"),
      });
      return false;
    }
  },

  disconnect: () => {
    set({
      connection: null,
      notice: "API Key 已从当前页面内存中清除",
    });
  },

  createGoalAndStart: async (draft) => {
    const connection = get().connection;
    if (!connection) {
      set({ error: "请先连接模型" });
      return;
    }
    const goal = createLearningGoal(draft);
    await goalRepository.save(goal);
    await goalRepository.setActiveGoalId(goal.goal_id);
    set((state) => ({
      goals: [goal, ...state.goals],
      activeGoal: goal,
      focusedTurnId: null,
      currentTurnId: null,
      focusedBranchId:
        goal.local_state.conversation.main_branch_id,
      forceFork: false,
      goalEditorOpen: false,
      notice: "学习目标已创建，正在生成学习规划",
    }));
    await get().sendTurn(
      "请根据我的背景、学习目标和目标程度，制定一份分点学习规划。暂时不要展开第一点，先让我确认规划。",
      "auto",
    );
  },

  selectGoal: async (goalId) => {
    const goal =
      get().goals.find((item) => item.goal_id === goalId) ?? null;
    if (!goal) {
      return;
    }
    await goalRepository.setActiveGoalId(goalId);
    set({
      activeGoal: goal,
      focusedTurnId: goal.local_state.active_head_turn_id,
      currentTurnId: goal.local_state.active_head_turn_id,
      focusedBranchId: goal.local_state.active_branch_id,
      forceFork: false,
      error: null,
    });
  },

  focusTurn: (turnId) => {
    const goal = get().activeGoal;
    if (!goal) {
      return;
    }
    const branch = findSourceBranch(
      goal.local_state.conversation,
      turnId,
      get().focusedBranchId ??
        goal.local_state.active_branch_id,
    );
    set({
      focusedTurnId: turnId,
      focusedBranchId: branch.branch_id,
    });
  },

  activateTurn: (turnId) => {
    const goal = get().activeGoal;
    if (!goal) {
      return;
    }
    const conversation = goal.local_state.conversation;
    const branch = findSourceBranch(
      conversation,
      turnId,
      get().focusedBranchId ??
        goal.local_state.active_branch_id,
    );
    const turn = conversation.turns[turnId];
    if (
      turn.connection_kind === "root" &&
      branch.head_turn_id !== turnId
    ) {
      set({
        focusedTurnId: turnId,
        focusedBranchId: branch.branch_id,
        notice: "根节点已有后继，只能查看，不能从这里创建分支",
      });
      return;
    }
    set({
      focusedTurnId: turnId,
      currentTurnId: turnId,
      focusedBranchId: branch.branch_id,
      forceFork: false,
      notice:
        branch.head_turn_id === turnId
          ? "已切换到这条路径的末端"
          : "已定位到历史节点，下一次提问会从这里创建分支",
    });
  },

  setForceFork: (enabled) => set({ forceFork: enabled }),

  sendTurn: async (userText, retrievalMode) => {
    const {
      activeGoal,
      connection,
      currentTurnId,
      focusedBranchId,
      forceFork,
    } = get();
    if (!activeGoal || !connection) {
      set({ error: "当前没有可用的学习目标或模型连接" });
      return;
    }
    if (
      connection.provider !== activeGoal.runtime_model.provider ||
      connection.model !== activeGoal.runtime_model.model
    ) {
      set({
        error: `此目标固定使用 ${activeGoal.runtime_model.model}，请重新连接对应模型`,
      });
      return;
    }
    if (!userText.trim()) {
      return;
    }

    set({ busy: true, error: null, notice: null });
    try {
      const command = buildConversationCommand({
        goal: activeGoal,
        userText,
        sourceTurnId: currentTurnId ?? undefined,
        sourceBranchId: focusedBranchId ?? undefined,
        forceFork,
        retrievalMode,
      });
      const delta = await learningApiClient.executeTurn(
        command,
        connection.apiKey,
      );
      const updated = await goalRepository.applyDelta(
        activeGoal.goal_id,
        delta,
      );
      set((state) => ({
        activeGoal: updated,
        goals: state.goals.map((goal) =>
          goal.goal_id === updated.goal_id ? updated : goal,
        ),
        focusedTurnId: delta.next_active_head_turn_id,
        currentTurnId: delta.next_active_head_turn_id,
        focusedBranchId: delta.next_active_branch_id,
        forceFork: false,
        busy: false,
        notice:
          delta.warnings.length > 0
            ? delta.warnings.join("；")
            : "回答已保存到本地",
      }));
    } catch (error) {
      set({
        busy: false,
        error: messageOf(error, "发送失败，本地数据没有变化"),
      });
    }
  },

  openGoalEditor: () => set({ goalEditorOpen: true }),
  closeGoalEditor: () => set({ goalEditorOpen: false }),

  exportData: () => serializeBackup(get().goals),

  importData: async (raw) => {
    try {
      const backup = parseBackup(raw);
      for (const goal of backup.goals) {
        await goalRepository.save(goal);
      }
      const goals = await goalRepository.list();
      set({
        goals,
        activeGoal: goals[0] ?? null,
        focusedTurnId:
          goals[0]?.local_state.active_head_turn_id ?? null,
        currentTurnId:
          goals[0]?.local_state.active_head_turn_id ?? null,
        focusedBranchId:
          goals[0]?.local_state.active_branch_id ?? null,
        notice: `已导入 ${backup.goals.length} 个学习目标`,
        error: null,
      });
    } catch (error) {
      set({ error: messageOf(error, "导入失败") });
    }
  },

  clearFeedback: () => set({ error: null, notice: null }),
}));

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
