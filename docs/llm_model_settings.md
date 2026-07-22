## 模块名称：LLM 模型目录、选择与连接测试

### 📦 输出

- `app/llm/settings.py`：内置厂商字典、默认选择和 `LLMModel` 工厂。
- `app/services/llm_client.py`：统一适配 OpenAI Chat、OpenAI Responses 和 Anthropic Messages。
- `app/services/llm_connection_service.py`：发送严格的“连接成功”测试消息。
- `app/schemas/llm.py`：模型目录、内置选择和自定义预设的 HTTP 数据结构。
- `app/routes/llm.py`：暴露模型目录和无状态连接测试接口。
- `requirements.txt`：增加 Anthropic Python SDK。

### 🧩 解决的问题

模型的固定资料原先需要由调用者逐项填写。现在 SDK、Base URL、模型清单、输出上限和官方文档统一保存在内置目录中。浏览器只需要保存厂商、具体模型和 API Key；聊天、压缩等下游始终只接收统一的 `LLMModel`。

### ✅ 完成的功能

- [x] 默认使用 `MiniMax-M3`。
- [x] 内置 DeepSeek、GPT、Claude、Grok、GLM 和 MiniMax。
- [x] 支持 OpenAI Chat Completions、OpenAI Responses 和 Anthropic Messages。
- [x] 支持浏览器提交自定义预设，不在后端保存 API Key。
- [x] 返回每个厂商的官方文档地址和支持模型。
- [x] 连接测试严格要求模型只返回“连接成功”。
- [x] API Key 使用 `SecretStr` 接收，不出现在接口响应中。

### ⚡ 暴露的函数/接口

- `build_llm_model(provider: str, api_key: str, model: str | None = None) -> LLMModel`
- `build_custom_llm_model(*, name: str, adapter: LLMAdapter, api_key: str, base_url: str, model: str, max_tokens: int = 4096) -> LLMModel`
- `GET /llm/presets`
- `POST /llm/connection-test`

## 默认配置

`.env` 只需要保存默认选择和本地运行使用的 API Key：

```dotenv
DEFAULT_LLM_PROVIDER=minimax
DEFAULT_LLM_MODEL=MiniMax-M3
LLM_API_KEY=你的_API_KEY
```

如果省略 `DEFAULT_LLM_MODEL`，系统自动使用该厂商的默认模型。

## 获取模型目录

```http
GET /llm/presets
```

响应只包含公开资料，不包含 API Key：

```json
{
  "default_provider": "minimax",
  "default_model": "MiniMax-M3",
  "providers": [
    {
      "id": "minimax",
      "name": "MiniMax",
      "models": ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"],
      "default_model": "MiniMax-M3",
      "docs_url": "https://platform.minimaxi.com/docs/api-reference/text-chat-anthropic"
    }
  ]
}
```

## 测试内置预设

```http
POST /llm/connection-test
Content-Type: application/json
```

```json
{
  "provider": "minimax",
  "model": "MiniMax-M3",
  "api_key": "用户填写的 Key"
}
```

## 测试自定义预设

```json
{
  "api_key": "用户填写的 Key",
  "custom_preset": {
    "name": "自定义模型",
    "adapter": "openai_chat",
    "base_url": "https://example.com/v1",
    "model": "custom-model",
    "max_tokens": 4096,
    "docs_url": "https://example.com/docs"
  }
}
```

`adapter` 可选值：

- `openai_chat`
- `openai_responses`
- `anthropic`

连接测试按以下顺序选择模型：

1. 存在 `custom_preset` 时优先使用自定义预设。
2. 没有自定义预设时，使用请求中的 `provider` 和 `model`。
3. 请求未指定模型时，使用 `.env` 对应的默认模型；默认值是 `MiniMax-M3`。

自定义 Base URL 当前适合本地个人使用；公开部署前需要增加内网地址拦截，避免服务端请求伪造风险。
