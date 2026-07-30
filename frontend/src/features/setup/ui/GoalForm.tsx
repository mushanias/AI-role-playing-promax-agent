import { useState } from "react";

import { useAppStore } from "../../../app/useAppStore";
import {
  BUILTIN_LEARNING_PROMPTS,
  createCustomPrompt,
} from "../../goals/application/prompts";

interface GoalFormProps {
  onCancel?: () => void;
}

export function GoalForm({ onCancel }: GoalFormProps) {
  const connection = useAppStore((state) => state.connection);
  const busy = useAppStore((state) => state.busy);
  const createGoalAndStart = useAppStore(
    (state) => state.createGoalAndStart,
  );
  const [name, setName] = useState("");
  const [background, setBackground] = useState("");
  const [learningGoal, setLearningGoal] = useState("");
  const [targetLevel, setTargetLevel] = useState("");
  const [timeBudget, setTimeBudget] = useState("");
  const [promptId, setPromptId] = useState(
    BUILTIN_LEARNING_PROMPTS[0].prompt_id,
  );
  const [customPromptName, setCustomPromptName] = useState("我的学习方式");
  const [customPrompt, setCustomPrompt] = useState("");
  const isCustom = promptId === "custom";

  const valid =
    connection &&
    name.trim() &&
    background.trim() &&
    learningGoal.trim() &&
    targetLevel.trim() &&
    (!isCustom ||
      (customPromptName.trim() && customPrompt.trim()));

  async function submit() {
    if (!connection || !valid) {
      return;
    }
    const prompt = isCustom
      ? createCustomPrompt(customPromptName, customPrompt)
      : BUILTIN_LEARNING_PROMPTS.find(
          (item) => item.prompt_id === promptId,
        )!;
    await createGoalAndStart({
      name,
      background,
      learningGoal,
      targetLevel,
      timeBudget,
      prompt,
      runtimeModel: {
        provider: connection.provider,
        model: connection.model,
      },
    });
  }

  return (
    <section className="goal-form">
      <div className="eyebrow">02 · 学习目标</div>
      <h1>告诉我这次要走到哪里</h1>
      <p className="section-lead">
        背景、目标与学习方式会作为本目标的固定底座。填错时新建目标，不污染已有路径。
      </p>

      <label>
        <span>给这个目标起个名字</span>
        <input
          value={name}
          placeholder="例如：2027 数学一"
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label>
        <span>你现在的背景</span>
        <textarea
          value={background}
          placeholder="已经学过什么、目前哪里吃力……"
          onChange={(event) => setBackground(event.target.value)}
        />
      </label>
      <div className="field-grid two">
        <label>
          <span>想学习什么</span>
          <input
            value={learningGoal}
            placeholder="具体主题或考试目标"
            onChange={(event) => setLearningGoal(event.target.value)}
          />
        </label>
        <label>
          <span>希望达到什么程度</span>
          <input
            value={targetLevel}
            placeholder="入门、能做题、能独立应用……"
            onChange={(event) => setTargetLevel(event.target.value)}
          />
        </label>
      </div>
      <label>
        <span>可选：时间安排</span>
        <input
          value={timeBudget}
          placeholder="例如：每天 2 小时，持续 4 个月"
          onChange={(event) => setTimeBudget(event.target.value)}
        />
      </label>

      <fieldset className="prompt-picker">
        <legend>选择学习方式</legend>
        {[...BUILTIN_LEARNING_PROMPTS, null].map((prompt) => {
          const id = prompt?.prompt_id ?? "custom";
          return (
            <label
              className={`prompt-option ${
                promptId === id ? "selected" : ""
              }`}
              key={id}
            >
              <input
                type="radio"
                name="prompt"
                value={id}
                checked={promptId === id}
                onChange={() => setPromptId(id)}
              />
              <span>
                <strong>{prompt?.name ?? "自定义"}</strong>
                <small>
                  {prompt?.content.slice(0, 54) ??
                    "完全使用你自己的学习提示词"}
                  …
                </small>
              </span>
            </label>
          );
        })}
      </fieldset>

      {isCustom && (
        <div className="custom-prompt-fields">
          <label>
            <span>学习方式名称</span>
            <input
              value={customPromptName}
              onChange={(event) =>
                setCustomPromptName(event.target.value)
              }
            />
          </label>
          <label>
            <span>自定义 Prompt</span>
            <textarea
              className="tall"
              value={customPrompt}
              placeholder="描述 AI 应该怎样规划、讲解和检查学习效果"
              onChange={(event) => setCustomPrompt(event.target.value)}
            />
          </label>
        </div>
      )}

      <div className="form-actions">
        {onCancel && (
          <button className="button ghost" onClick={onCancel}>
            取消
          </button>
        )}
        <button
          className="button primary"
          disabled={!valid || busy}
          onClick={submit}
        >
          {busy ? "正在创建…" : "创建并生成规划"}
        </button>
      </div>
    </section>
  );
}
