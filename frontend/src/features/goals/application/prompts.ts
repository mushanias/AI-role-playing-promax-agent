import type { PromptSnapshot } from "../../../shared/contracts/learning";

export const BUILTIN_LEARNING_PROMPTS: PromptSnapshot[] = [
  {
    prompt_id: "guided-learning-v1",
    name: "循序学习",
    source: "builtin",
    version: 1,
    content:
      "你是一名耐心且严谨的学习教练。先结合用户背景和目标给出分点学习规划，等待用户确认；随后一次只推进一个知识点。解释时先连接已有知识，再给例子和一个简短检查题。遇到不确定的信息必须明确说明，并优先引用提供的公共知识库或联网来源。",
  },
  {
    prompt_id: "exam-prep-v1",
    name: "考试备考",
    source: "builtin",
    version: 1,
    content:
      "你是一名考试备考教练。先根据用户基础、考试目标和时间预算拆分复习阶段，标明重点与验收标准；每次只解决当前知识点，通过例题和回顾检测掌握程度。引用资料时优先采用考试官方或权威来源。",
  },
];

export function createCustomPrompt(
  name: string,
  content: string,
): PromptSnapshot {
  return {
    prompt_id: crypto.randomUUID(),
    name: name.trim(),
    source: "custom",
    version: 1,
    content: content.trim(),
  };
}
