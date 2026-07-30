import { LearningApiClient } from "../features/chat/api/learningClient";
import { GoalRepository } from "../features/goals/storage/goalRepository";

/** 应用级基础设施只在组合根创建，业务组件只通过状态动作使用。 */
export const goalRepository = new GoalRepository();
export const learningApiClient = new LearningApiClient(
  import.meta.env.VITE_API_BASE_URL || "/api",
);
