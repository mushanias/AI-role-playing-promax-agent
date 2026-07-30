import { openDB, type IDBPDatabase } from "idb";

import type { ConversationDelta } from "../../../shared/contracts/learning";
import type { LearningGoal } from "../domain/models";
import {
  DEFAULT_DATABASE_NAME,
  type LearningAgentDatabase,
} from "./schema";

export class LocalRevisionConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LocalRevisionConflictError";
  }
}

/** 所有本地会话写入都集中在这里，界面不直接操作 IndexedDB。 */
export class GoalRepository {
  private databasePromise: Promise<
    IDBPDatabase<LearningAgentDatabase>
  > | null = null;

  constructor(
    private readonly databaseName = DEFAULT_DATABASE_NAME,
  ) {}

  async list(): Promise<LearningGoal[]> {
    const database = await this.database();
    const goals = await database.getAllFromIndex(
      "goals",
      "by-updated-at",
    );
    return goals.reverse();
  }

  async get(goalId: string): Promise<LearningGoal | undefined> {
    return (await this.database()).get("goals", goalId);
  }

  async save(goal: LearningGoal): Promise<void> {
    await (await this.database()).put("goals", structuredClone(goal));
  }

  async remove(goalId: string): Promise<void> {
    const database = await this.database();
    const transaction = database.transaction(
      ["goals", "preferences"],
      "readwrite",
    );
    const active = await transaction
      .objectStore("preferences")
      .get("active-goal-id");
    await transaction.objectStore("goals").delete(goalId);
    if (active?.value === goalId) {
      await transaction.objectStore("preferences").put({
        key: "active-goal-id",
        value: null,
      });
    }
    await transaction.done;
  }

  async getActiveGoalId(): Promise<string | null> {
    const record = await (await this.database()).get(
      "preferences",
      "active-goal-id",
    );
    return record?.value ?? null;
  }

  async setActiveGoalId(goalId: string | null): Promise<void> {
    await (await this.database()).put("preferences", {
      key: "active-goal-id",
      value: goalId,
    });
  }

  async applyDelta(
    goalId: string,
    delta: ConversationDelta,
  ): Promise<LearningGoal> {
    const database = await this.database();
    const transaction = database.transaction("goals", "readwrite");
    const store = transaction.store;
    const goal = await store.get(goalId);
    if (!goal) {
      throw new Error("要更新的学习目标不存在");
    }
    if (
      goal.local_state.applied_operation_ids.includes(
        delta.operation_id,
      )
    ) {
      await transaction.done;
      return goal;
    }

    const conversation = goal.local_state.conversation;
    if (conversation.revision !== delta.old_revision) {
      throw new LocalRevisionConflictError(
        `本地修订号为 ${conversation.revision}，增量要求 ${delta.old_revision}`,
      );
    }
    if (delta.new_revision !== delta.old_revision + 1) {
      throw new LocalRevisionConflictError("服务端增量修订号不连续");
    }

    for (const turn of delta.added_turns) {
      if (conversation.turns[turn.turn_id]) {
        throw new Error(`节点 ${turn.turn_id} 已存在`);
      }
      conversation.turns[turn.turn_id] = turn;
      if (turn.connection_kind === "root") {
        if (conversation.root_turn_id) {
          throw new Error("当前会话已经存在根节点");
        }
        conversation.root_turn_id = turn.turn_id;
      }
    }
    for (const branch of delta.added_branches) {
      if (conversation.branches[branch.branch_id]) {
        throw new Error(`分支 ${branch.branch_id} 已存在`);
      }
      conversation.branches[branch.branch_id] = branch;
    }
    for (const summary of delta.added_summaries) {
      conversation.summaries[summary.summary_id] = summary;
    }
    for (const citation of delta.added_citations) {
      conversation.citations[citation.citation_id] = citation;
    }
    for (const update of delta.branch_head_updates) {
      const branch = conversation.branches[update.branch_id];
      if (!branch) {
        throw new Error(`待更新的分支 ${update.branch_id} 不存在`);
      }
      if (branch.head_turn_id !== update.old_head_turn_id) {
        throw new LocalRevisionConflictError(
          `分支 ${update.branch_id} 的末端已变化`,
        );
      }
      branch.head_turn_id = update.new_head_turn_id;
      branch.active_summary_id = update.new_active_summary_id;
    }

    conversation.revision = delta.new_revision;
    goal.local_state.active_branch_id =
      delta.next_active_branch_id;
    goal.local_state.active_head_turn_id =
      delta.next_active_head_turn_id;
    goal.local_state.applied_operation_ids.push(
      delta.operation_id,
    );
    goal.updated_at = new Date().toISOString();
    await store.put(goal);
    await transaction.done;
    return goal;
  }

  async close(): Promise<void> {
    if (!this.databasePromise) {
      return;
    }
    (await this.databasePromise).close();
    this.databasePromise = null;
  }

  private database(): Promise<IDBPDatabase<LearningAgentDatabase>> {
    if (!this.databasePromise) {
      this.databasePromise = openDB<LearningAgentDatabase>(
        this.databaseName,
        1,
        {
          upgrade(database) {
            const goals = database.createObjectStore("goals", {
              keyPath: "goal_id",
            });
            goals.createIndex("by-updated-at", "updated_at");
            database.createObjectStore("preferences", {
              keyPath: "key",
            });
          },
        },
      );
    }
    return this.databasePromise;
  }
}
