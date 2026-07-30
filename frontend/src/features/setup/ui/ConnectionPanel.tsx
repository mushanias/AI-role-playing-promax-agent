import { useEffect, useMemo, useState } from "react";

import { useAppStore } from "../../../app/useAppStore";

interface ConnectionPanelProps {
  title?: string;
  compact?: boolean;
}

export function ConnectionPanel({
  title = "先连接你自己的模型",
  compact = false,
}: ConnectionPanelProps) {
  const presets = useAppStore((state) => state.presets);
  const connectionBusy = useAppStore(
    (state) => state.connectionBusy,
  );
  const connect = useAppStore((state) => state.connect);
  const retryPresets = useAppStore((state) => state.retryPresets);
  const activeGoal = useAppStore((state) => state.activeGoal);
  const [provider, setProvider] = useState(
    activeGoal?.runtime_model.provider ??
      presets?.default_provider ??
      "",
  );
  const [model, setModel] = useState(
    activeGoal?.runtime_model.model ?? presets?.default_model ?? "",
  );
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    if (activeGoal) {
      setProvider(activeGoal.runtime_model.provider);
      setModel(activeGoal.runtime_model.model);
      return;
    }
    if (presets && !provider) {
      setProvider(presets.default_provider);
      setModel(presets.default_model);
    }
  }, [activeGoal, presets, provider]);

  const providerPreset = useMemo(
    () => presets?.providers.find((item) => item.id === provider),
    [presets, provider],
  );

  function changeProvider(nextProvider: string) {
    const next = presets?.providers.find(
      (item) => item.id === nextProvider,
    );
    setProvider(nextProvider);
    setModel(next?.default_model ?? "");
  }

  if (!presets) {
    return (
      <section className="connection-panel">
        <p>还没有读到模型列表。</p>
        <button className="button primary" onClick={() => retryPresets()}>
          重新连接后端
        </button>
      </section>
    );
  }

  return (
    <section
      className={`connection-panel ${compact ? "compact" : ""}`}
    >
      <div className="eyebrow">01 · 模型连接</div>
      <h1>{title}</h1>
      <p className="section-lead">
        API Key 只在当前页面内存中用于发请求，刷新或关闭页面后即消失。
      </p>

      <div className="field-grid two">
        <label>
          <span>模型厂商</span>
          <select
            value={provider}
            disabled={Boolean(activeGoal)}
            onChange={(event) => changeProvider(event.target.value)}
          >
            {presets.providers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>模型</span>
          <select
            value={model}
            disabled={Boolean(activeGoal)}
            onChange={(event) => setModel(event.target.value)}
          >
            {providerPreset?.models.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label>
        <span>API Key</span>
        <div className="secret-input">
          <input
            autoComplete="off"
            type={showKey ? "text" : "password"}
            value={apiKey}
            placeholder="粘贴后只保留在本页内存"
            onChange={(event) => setApiKey(event.target.value)}
          />
          <button
            type="button"
            className="text-button"
            onClick={() => setShowKey((value) => !value)}
          >
            {showKey ? "隐藏" : "显示"}
          </button>
        </div>
      </label>

      <div className="form-actions">
        {providerPreset?.docs_url && (
          <a
            className="text-link"
            href={providerPreset.docs_url}
            target="_blank"
            rel="noreferrer"
          >
            查看厂商文档 ↗
          </a>
        )}
        <button
          className="button primary"
          disabled={!apiKey.trim() || connectionBusy}
          onClick={() =>
            connect({
              apiKey: apiKey.trim(),
              provider,
              model,
            })
          }
        >
          {connectionBusy ? "正在验证…" : "测试并连接"}
        </button>
      </div>
    </section>
  );
}
