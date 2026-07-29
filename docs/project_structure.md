# 通用会话内核结构

## 模块职责

- `app/conversations/`：版本化会话、消息生命周期、分支与历史视图。
- `app/conversations/memory/`：Context 规划、Token 水位、摘要版本和降级。
- `app/llm/`：模型配置、统一客户端和连接测试。
- `app/storage/`：与领域无关的 JSON 文件存储。
- `app/core/`：配置、依赖装配、日志和错误映射。
- `app/exceptions/`：应用层异常。

## 依赖方向

```text
HTTP routes
→ ConversationService
→ BranchService / VersionedChatService
→ VersionedContextManager
→ ContextPlanner / CompressionService
→ ConversationRepository / LLMClient
→ JsonFileStore
```

会话内核不依赖任何具体产品模块。未来产品模块可以调用会话内核，
但会话内核不能反向导入产品级项目、资产或工作流。

## 持久化边界

当前每个会话保存为：

```text
data/conversations/{conversation_id}.json
```

运行时数据不进入 Git。具体产品需要的项目数据应使用独立目录和模型，
不能作为全局设定注入所有会话。
