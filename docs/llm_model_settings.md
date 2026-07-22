## 模块名称：LLM 模型配置

### 📦 输出

- `app/llm/settings.py`：定义模型配置类型和当前模型。
- `app/llm/__init__.py`：提供统一导入入口。
- `app/core/dependencies.py`：改为通过统一入口读取模型配置。
- `app/core/config.py`：移除原先混在通用配置中的 DeepSeek 配置。

### 🧩 解决的问题

LLM 的 API Key、接口地址和模型名称原先位于通用配置模块中，切换模型时需要了解依赖组装细节。现在这些设置集中在独立目录，并通过单一对象暴露。

### ✅ 完成的功能

- [x] 通过 `llm_model` 统一提供 LLM 连接配置。
- [x] 支持通过 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL` 切换模型。
- [x] 兼容现有的 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 环境变量。
- [x] 主对话与历史压缩继续共用同一个 LLM 客户端，不改变已有行为。

### ⚡ 暴露的函数/接口

- `LLMModel(api_key: str, base_url: str, model: str)`
- `llm_model: LLMModel`
- 统一导入方式：`from app.llm import llm_model`
