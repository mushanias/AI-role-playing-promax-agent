# 上下文与压缩机制重构交付文档（07）

## 模块名称：版本化 ChatService 与 Turn 生命周期

### 📦 输出

- `app/models/chat_turn.py`：新增一次完整聊天调用的返回模型。
- `app/models/__init__.py`：导出 `ChatTurnResult`。
- `app/services/versioned_chat_service.py`：新增按 Turn 状态工作的聊天编排服务。
- `app/services/__init__.py`：导出 `VersionedChatService`。
- `test/test_versioned_chat_service.py`：验证 pending、completed、failed 和分支隔离。

旧 `ChatService` 暂时保留，供尚未改造的 `/chat` 接口使用。新 API 完成后再切换依赖并移除旧消息写入链路。

### 🧩 解决的问题

旧聊天服务把用户消息和助手消息分别追加到一个扁平数组，无法表达完整轮次、分支 HEAD 或生成中的用户输入。本模块将一次聊天改成明确的状态机：

```text
用户发送
→ 原子创建 pending Turn，挂到目标 Branch.pending_turn_id
→ ContextManager 读取该 pending Turn 作为当前输入
→ 主 LLM 返回
→ 原子写入助手回复，把 Turn 改为 completed
→ Branch.HEAD 前进到新 Turn，清空 pending 指针
```

如果 Context 构建、压缩或主 LLM 调用失败，则保留用户原文，把 Turn 标记为 `failed`，清空 pending 指针，并让 HEAD 停留在上一轮。Turn 使用稳定 UUID，历史关系只依赖 `parent_turn_id`，因此不存在连续数字 ID “跳号”导致指针损坏的问题。

### ✅ 完成的功能

- [x] 支持向活动分支发送消息。
- [x] 支持显式指定目标分支发送消息。
- [x] 在任何 LLM 调用前先持久化用户原文。
- [x] pending Turn 的 `parent_turn_id` 等于目标分支当前 HEAD。
- [x] ContextManager 构建时能够读取本轮 pending 用户输入。
- [x] 主 LLM 成功后保存助手回复并把 Turn 改为 completed。
- [x] 只有 completed Turn 才能成为新的 Branch HEAD。
- [x] 成功后清空 `Branch.pending_turn_id`。
- [x] Context 或主 LLM 失败时保留原始用户输入并标记 failed。
- [x] 失败时 HEAD 不前进，并清空 pending 指针，允许用户继续发送。
- [x] 请求取消时尽力保存 failed 状态，避免分支永久卡在 pending。
- [x] 同一分支已有 pending Turn 时拒绝并发创建第二个 pending Turn。
- [x] 不修改其他分支的 HEAD、pending 或摘要指针。
- [x] 将 Context 警告、压缩次数和质量降级状态返回给上层。

### ⚡ 暴露的函数/接口

#### `ChatTurnResult`

```python
@dataclass(frozen=True)
class ChatTurnResult:
    conversation_id: str
    branch_id: str
    turn_id: str
    reply: str
    warnings: tuple[str, ...]
    compression_passes: int
    quality_degraded: bool
```

输出：完成轮次的稳定 ID、所属分支、助手回复，以及后续 API 用于弹出提示的 Context 质量信息。

#### `VersionedChatService`

```python
class VersionedChatService:
    async def send(
        self,
        conversation_id: str,
        user_input: str,
        branch_id: str | None = None,
    ) -> ChatTurnResult: ...
```

输入：会话 ID、用户原始输入和可选目标分支 ID。

输出：`ChatTurnResult`。调用成功代表对应 Turn 已经持久化为 completed；调用抛出 LLM 或存储异常时，服务会先尽力把已经创建的 pending Turn 标记为 failed，再把原异常交给 API 层处理。

验证方式：

1. 在假 LLM 内读取 JSON，确认调用发生时用户 Turn 已经是 pending。
2. LLM 成功后确认助手回复、completed 状态和 Branch HEAD 一次提交。
3. LLM 抛出异常后确认用户原文仍存在、Turn 为 failed、HEAD 未移动。
4. 在非活动分支发送消息，确认只有目标分支发生变化。
5. 同一分支预先存在 pending Turn，确认不会创建第二个 Turn。
6. ContextManager 返回 warning，确认 `ChatTurnResult` 原样向上透传。
