import type { DBSchema } from "idb";

import type { LearningGoal } from "../domain/models";

export interface LearningAgentDatabase extends DBSchema {
  goals: {
    key: string;
    value: LearningGoal;
    indexes: {
      "by-updated-at": string;
    };
  };
  preferences: {
    key: string;
    value: {
      key: string;
      value: string | null;
    };
  };
}

export const DEFAULT_DATABASE_NAME = "learning-agent-local-v1";
