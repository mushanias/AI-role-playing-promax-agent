# 项目结构重组交付文档

## 模块名称：按业务功能组织的模块化单体

### 📦 输出

- `app/main.py`：唯一 FastAPI 应用入口。
- `app/conversations/`：会话聚合、剧情分支、消息发送、持久化与 HTTP 接口。
- `app/conversations/memory/`：会话内部的 Context 规划、压缩和 Prompt。
- `app/profile/`：独立生命周期的全局角色设定。
- `app/llm/`：模型设置、连接测试、SDK 调用和 HTTP 接口。
- `app/storage/json_file_store.py`：跨模块复用的底层 JSON 文件读写。
- `app/core/`、`app/exceptions/`：全局组装、配置、日志和异常契约。

### 🧩 解决的问题

原结构按 `routes`、`schemas`、`models`、`services` 和 `storage`
等技术类型横向分层，阅读一条会话业务链时需要频繁跨目录跳转。
本模块按业务所有权重新组织文件，让 Conversation 聚合其 Memory
能力，同时保留 Profile、LLM 和通用存储的独立生命周期。

### ✅ 完成的功能

- [x] 保持全部 HTTP 路径、请求结构和响应结构不变。
- [x] 保持领域模型、服务实现和 JSON 数据格式不变。
- [x] 将会话相关代码聚合到 `app/conversations/`。
- [x] 将 Context 与压缩代码放入 `app/conversations/memory/`。
- [x] 将 Profile 与 LLM 分别聚合为独立业务模块。
- [x] 统一 `app/main.py` 为唯一 FastAPI 入口。
- [x] 更新应用、测试和当前文档中的导入路径。

### ⚡ 暴露的函数/接口

- FastAPI 应用：`app.main:app`
- 会话 Router：`app.conversations.routes.router`
- Profile Router：`app.profile.routes.router`
- LLM Router：`app.llm.routes.router`
- HTTP API 路径与重组前保持一致。
