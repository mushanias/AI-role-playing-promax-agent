# 上下文与压缩机制重构交付文档（09）

## 模块名称：后端 MVP 最终接线与验收

### 📦 输出

- `app/models/context_plan.py`：为 `ManagedContext` 增加仅用于本轮发送的降级载荷。
- `app/services/context_builder.py`：移除无效的重复预算参数，水位统一由 ContextPlanner 管理。
- `app/services/versioned_context_manager.py`：增加完整 Turn 优先的发送载荷降级策略。
- `app/core/error_mapping.py`：新增领域异常到 HTTP 状态码和稳定错误码的映射。
- `app/services/llm_compressor.py`：依赖最小 LLM Protocol，不再为类型标注强制加载 OpenAI SDK。
- `app/services/llm_client.py`：统一转换限流、拒绝请求、异常状态和空候选回复。
- `app/api.py`：只注册新版会话路由，并使用统一错误响应。
- `app/core/config.py`、`app/core/dependencies.py`：移除旧线性消息链路配置与装配。
- `app/main.py`：CLI 切换到新版会话服务，并在单一事件循环中运行。
- `README.md`：更新数据结构、配置、启动方式和全部后端接口。
- `.gitignore`：忽略运行时日志目录。
- `test/test_backend_end_to_end.py`：验证创建、发送、压缩、重写、切换和极端输入降级的完整链路。
- `test/test_error_mapping.py`：验证 HTTP 错误契约。
- 删除旧 `/chat`、线性消息存储、单摘要 `ContextState`、按消息数压缩及过时手工脚本；Git 历史仍可恢复这些文件。

### 🧩 解决的问题

新版模块已经能够独立工作，但旧 `/chat` 仍会把消息写入 `chat_history.json`，与新的 Conversation JSON 形成两套互不相容的真实来源。最终版必须只保留一条正式写入链路：

```text
/conversations API
→ ConversationService
→ VersionedChatService
→ VersionedContextManager
→ ConversationRepository
→ data/conversations/{conversation_id}.json
```

此外，“无法压缩时不抛预算错误”还不足以保证供应商接受请求。本模块增加只作用于本次 LLM 请求的降级载荷：

```text
超过高水位且无法继续压缩
→ 依次省略最早的完整 raw Turn
→ 仍超限时省略摘要
→ 当前输入或全局设定单独超限时截短发送副本
→ JSON 中原始 Turn、摘要和 profile 均不修改
→ 成功响应通过 warnings 告知界面
```

常规压缩仍然绝不切断 Turn。只有极端内容本身超过发送上限时，才截短临时副本，并同时保留内容首尾和明确标记。

### ✅ 完成的功能

- [x] 新版 `/conversations` 成为唯一正式聊天写入入口。
- [x] 移除会产生第二份历史真相的旧 `/chat` 路由。
- [x] 移除旧线性消息、单摘要状态和按消息数压缩运行时代码。
- [x] 保留 ProfileStorage、JsonFileStore 和新版 ConversationRepository。
- [x] CLI 使用新版会话创建与发送流程。
- [x] CLI 在同一 asyncio 事件循环中复用仓库锁和 LLM 客户端。
- [x] 默认质量高水位为 40k。
- [x] 默认压缩软目标为 25k。
- [x] 默认近期原文目标为 10k。
- [x] Context 水位只有 ContextPlanner 一份真实配置来源。
- [x] 常规压缩和降级优先在完整 Turn 边界工作。
- [x] 极端输入仅截短发送副本，JSON 原文完整保留。
- [x] 降级结果的实际估算不超过质量高水位。
- [x] 超长场景使用成功响应 warnings，不使用预算错误。
- [x] 资源不存在返回 404，状态冲突返回 409。
- [x] LLM 上游认证/响应错误返回 502，网络错误返回 503。
- [x] OpenAI 兼容 SDK 的限流与状态异常不会以未结构化异常穿透 API。
- [x] 存储损坏与 IO 错误返回 500。
- [x] README 覆盖数据文件、配置、全部 API 和错误契约。
- [x] 端到端验证压缩后原始 Turn 仍存在。
- [x] 端到端验证修改旧轮次后旧分支仍可切回。

### ⚡ 暴露的函数/接口

#### `ManagedContext`

```python
@dataclass(frozen=True)
class ManagedContext:
    candidate: ContextCandidate
    warnings: tuple[str, ...]
    compression_passes: int
    degraded_messages: tuple[dict[str, str], ...] | None = None
    degraded_estimated_tokens: int | None = None

    @property
    def messages(self) -> tuple[dict[str, str], ...]: ...

    @property
    def estimated_tokens(self) -> int: ...

    @property
    def quality_degraded(self) -> bool: ...
```

`candidate` 始终描述完整持久化语义；`messages` 在必要时返回临时降级副本。两者分离可以保证“发送效果允许下降”和“原始历史永不删除”同时成立。

#### `map_app_exception`

```python
def map_app_exception(error: BaseAppException) -> ErrorDescriptor: ...
```

输出：`status_code`、稳定 `code` 和可显示 `message`。HTTP 响应格式：

```json
{
  "error": {
    "code": "invalid_branch_operation",
    "message": "当前剧情分支已有正在生成的轮次"
  }
}
```

#### 正式 HTTP API

- `POST /conversations`
- `GET /conversations/{conversation_id}/history`
- `POST /conversations/{conversation_id}/turns`
- `POST /conversations/{conversation_id}/turns/{turn_id}/rewrite`
- `GET /conversations/{conversation_id}/turns/{turn_id}/variants`
- `POST /conversations/{conversation_id}/branches/{branch_id}/activate`
- Profile CRUD 路由保持不变。

验证方式：

1. 使用真实 JSON 仓库和全部新版服务、假 LLM，连续发送直到触发摘要。
2. 确认摘要追加、所有原始 Turn 仍存在。
3. 修改已经被摘要覆盖的旧轮次，确认新分支的摘要指针按规则回退。
4. 查询兄弟版本并切回旧分支，确认旧结局完整恢复。
5. 发送单条超过高水位的极端输入，确认主 LLM 收到受限副本，而 JSON 保存完整输入。
6. 验证错误类型到 404、409、502、503、500 的映射。
7. 运行完整单元测试、Python 编译检查和 FastAPI 路由注册冒烟测试。
