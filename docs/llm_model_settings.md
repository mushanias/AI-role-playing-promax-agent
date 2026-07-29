## 模块名称：LLM 模型参数与连接测试

### 📦 输出

- `app/llm/settings.py`：按 SDK 文档写好的模型参数字典，以及统一的 `llm_model`。
- `app/llm/client.py`：判断 SDK，并将字典参数直接发送给 SDK。
- `app/llm/connection_service.py`：发送严格的“连接成功”测试消息。
- `app/llm/schemas.py`：模型选择、自定义设置和 API Key 的 HTTP 数据结构。
- `app/llm/routes.py`：暴露模型列表和无状态连接测试接口。

### 🧩 解决的问题

浏览器只填写 API Key 并选择模型。后端从 `MODEL_SETTINGS` 取出已经写好的参数，覆盖 API Key 和模型名称后直接发送；聊天和压缩等下游始终只使用 `llm_model`，不判断具体厂商。

### ✅ 完成的功能

- [x] 默认使用 `MiniMax-M3`。
- [x] 内置 DeepSeek、GPT、Claude、Grok、GLM 和 MiniMax 参数。
- [x] `client_params` 直接传入 SDK 客户端。
- [x] `request_params` 直接传入模型请求。
- [x] 自定义设置优先，未填写自定义设置时使用所选或默认模型。
- [x] API Key 只参与本次请求，不出现在接口响应中。
- [x] 连接测试要求模型只返回“连接成功”。

### ⚡ 暴露的函数/接口

- `MODEL_SETTINGS: dict[str, dict]`
- `build_llm_model(api_key: str, provider: str | None = None, model: str | None = None, custom_setting: dict | None = None) -> dict`
- `llm_model: dict`
- `GET /llm/presets`
- `POST /llm/connection-test`

## 参数表结构

每个模型配置都直接使用 SDK 的参数名称：

```python
"minimax": {
    "name": "MiniMax",
    "sdk": "anthropic",
    "models": ("MiniMax-M3",),
    "client_params": {
        "base_url": "https://api.minimaxi.com/anthropic",
    },
    "request_params": {
        "model": "MiniMax-M3",
        "max_tokens": 4096,
    },
}
```

运行时只增加用户填写的 Key：

```python
client = anthropic.AsyncAnthropic(**llm_model["client_params"])
response = await client.messages.create(
    messages=messages,
    **llm_model["request_params"],
)
```

## 默认配置

```dotenv
DEFAULT_LLM_PROVIDER=minimax
DEFAULT_LLM_MODEL=MiniMax-M3
LLM_API_KEY=你的_API_KEY
```

如果没有填写默认厂商和模型，自动使用 MiniMax-M3。

## 获取模型目录

```http
GET /llm/presets
```

响应包含模型选项和文档地址，不包含 API Key。

## 测试默认或内置模型

只填写 Key 时测试默认 MiniMax-M3：

```json
{
  "api_key": "用户填写的 Key"
}
```

选择其他模型时：

```json
{
  "api_key": "用户填写的 Key",
  "provider": "glm",
  "model": "glm-5.2"
}
```

## 测试自定义设置

```json
{
  "api_key": "用户填写的 Key",
  "custom_preset": {
    "name": "自定义模型",
    "sdk": "openai_chat",
    "base_url": "https://example.com/v1",
    "model": "custom-model",
    "max_tokens": 4096
  }
}
```

`sdk` 支持 `openai_chat`、`openai_responses` 和 `anthropic`。为兼容已有请求，自定义设置暂时也接受旧字段名 `adapter`。

选择顺序只有一条规则：存在 `custom_preset` 就使用自定义设置，否则使用所选模型；没有选择时使用默认 MiniMax-M3。
