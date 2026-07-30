import type { LearningGoal } from "../domain/models";

export interface LearningBackup {
  schema_version: 1;
  exported_at: string;
  goals: LearningGoal[];
}

export function serializeBackup(goals: LearningGoal[]): string {
  return JSON.stringify(
    {
      schema_version: 1,
      exported_at: new Date().toISOString(),
      goals,
    } satisfies LearningBackup,
    null,
    2,
  );
}

export function parseBackup(raw: string): LearningBackup {
  const value: unknown = JSON.parse(raw);
  if (!isRecord(value) || value.schema_version !== 1) {
    throw new Error("备份版本不受支持");
  }
  if (!Array.isArray(value.goals)) {
    throw new Error("备份中缺少学习目标列表");
  }
  if (containsSecretField(value)) {
    throw new Error("备份中包含不应持久化的 API Key 字段");
  }
  for (const goal of value.goals) {
    if (
      !isRecord(goal) ||
      typeof goal.goal_id !== "string" ||
      !isRecord(goal.local_state)
    ) {
      throw new Error("备份中的学习目标格式无效");
    }
  }
  return value as unknown as LearningBackup;
}

function containsSecretField(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(containsSecretField);
  }
  if (!isRecord(value)) {
    return false;
  }
  return Object.entries(value).some(
    ([key, child]) =>
      ["api_key", "apiKey", "secret"].includes(key) ||
      containsSecretField(child),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
