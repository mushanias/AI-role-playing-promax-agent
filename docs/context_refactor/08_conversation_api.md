# 上下文与压缩机制重构交付文档（08）

## 模块名称：对话历史与分支 API

### 📦 输出

- `app/models/conversation_view.py`：新增界面使用的完整原文历史视图。
- `app/models/__init__.py`：导出历史视图模型。
- `app/services/conversation_service.py`：组合会话创建、历史读取、消息发送、重写和分支切换。
- `app/services/__init__.py`：导出 `ConversationService`。
- `app/schemas/conversation.py`：定义版本化会话的 HTTP 请求与响应。
- `app/schemas/__init__.py`：导出新增 Schema。
- `app/routes/conversations.py`：新增 `/conversations` 路由组。
- `app/routes/__init__.py`、`app/api.py`：注册新路由。
- `app/core/dependencies.py`：组装并缓存新版服务依赖。
- `app/services/token_counter.py`：延迟加载分词器，使应用导入与非 LLM 路由不必提前初始化二进制依赖。
- `test/test_conversation_service.py`：验证历史视图、重写和分支切换用例。

旧 `/chat` 仍然保留。本模块提供一组可独立使用的新接口，最终验收模块再决定旧接口的兼容与清理方式。

### 🧩 解决的问题

前端需要的不是摘要，而是当前剧情分支上的完整原文。它还需要知道每轮是否存在兄弟版本，才能决定是否显示左右箭头。本模块把领域对象转换为稳定的前端契约：

```text
Conversation JSON
→ 沿 Branch.HEAD 和 Turn.parent_turn_id 回溯
→ 返回按正序排列的完整 Turn
→ 统计相同 parent_turn_id 的 completed 兄弟 Turn
→ variant_count > 1 时界面显示左右箭头
```

修改第 N 轮时，接口先调用 `create_branch_for_rewrite()`，使新分支 HEAD 回到第 N-1 轮并执行摘要隔一轮回退，再把修改后的文本交给 `VersionedChatService.send()`。旧分支和旧 Turn 不删除。

### ✅ 完成的功能

- [x] 创建带空根分支的新会话。
- [x] 读取活动分支的完整原文历史。
- [x] 显式读取指定分支历史，不改变活动分支。
- [x] 历史响应包含 completed Turn 和当前 pending Turn。
- [x] 历史响应不使用摘要覆盖界面原文。
- [x] 每个 completed Turn 返回版本总数和当前版本下标。
- [x] `variant_count > 1` 时返回 `has_variants=true`，供界面显示箭头。
- [x] 向活动分支或指定分支发送消息。
- [x] 修改旧用户消息时从该 Turn 之前创建新分支。
- [x] 修改后立即在新分支生成新的完整 Turn。
- [x] 查询同一对话位置的全部完成版本及其代表分支。
- [x] 切换活动分支，不删除或作废其他分支。
- [x] 聊天响应携带超长 warning，供界面弹出提示。
- [x] 新依赖使用进程内单例 `ConversationRepository`，确保并发请求共享单会话锁。
- [x] `tiktoken` 延迟到创建 TokenCounter 时加载，不改变实际 Token 计算。
- [x] 新路由已注册，同时保留旧 `/chat`。

### ⚡ 暴露的函数/接口

#### `ConversationService`

```python
async def create_conversation() -> Conversation: ...
async def get_history(
    conversation_id: str,
    branch_id: str | None = None,
) -> ConversationHistory: ...
async def send_message(
    conversation_id: str,
    user_input: str,
    branch_id: str | None = None,
) -> ChatTurnResult: ...
async def rewrite_turn(
    conversation_id: str,
    target_turn_id: str,
    user_input: str,
    source_branch_id: str | None = None,
) -> ChatTurnResult: ...
async def list_turn_variants(
    conversation_id: str,
    turn_id: str,
) -> list[TurnVariant]: ...
async def activate_branch(
    conversation_id: str,
    branch_id: str,
) -> Branch: ...
```

#### HTTP API

- `POST /conversations`：创建会话。
- `GET /conversations/{conversation_id}/history`：读取活动或指定分支原文历史。
- `POST /conversations/{conversation_id}/turns`：发送新消息。
- `POST /conversations/{conversation_id}/turns/{turn_id}/rewrite`：修改旧消息并生成新分支。
- `GET /conversations/{conversation_id}/turns/{turn_id}/variants`：查询左右版本。
- `POST /conversations/{conversation_id}/branches/{branch_id}/activate`：切换活动分支。

验证方式：

1. 创建会话，确认返回会话 ID 和空根分支 ID。
2. 构造包含兄弟 Turn 的历史，确认原文顺序、版本数量和下标。
3. 修改第三轮，确认新分支 HEAD 从第二轮开始，并把新文本发往该分支。
4. 切换兄弟版本代表分支，确认活动历史随之变化。
5. 确认聊天 warning 能映射到 HTTP 响应。
6. 执行完整单元测试与 Python 编译检查。
