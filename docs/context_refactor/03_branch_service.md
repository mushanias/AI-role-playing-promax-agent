# 上下文与压缩机制重构交付文档（03）

## 模块名称：剧情分支服务

### 📦 输出

- `app/services/branch_service.py`：新增剧情分支与消息版本服务。
- `app/services/__init__.py`：导出 `BranchService` 和版本查询结果。
- `app/exceptions/branch_errors.py`：新增分支领域异常。
- `app/exceptions/__init__.py`：统一导出分支异常。
- `test/test_branch_service.py`：验证根分支、重写旧消息、摘要退层、版本箭头和分支切换。

本模块使用上一模块的 `ConversationRepository`，不直接读写 JSON 文件。

### 🧩 解决的问题

用户需要像普通聊天窗口一样查看消息，同时可以修改任意一条旧用户消息，生成不同结局。修改不能覆盖旧消息，也不能让用户接触摘要或内部历史指针。

MVP 固定语义：

```text
用户修改第 N 轮
→ 保留第 1 至 N-1 轮
→ 创建新 Branch
→ 后续由 ChatService 在新 Branch 写入新的第 N 轮
```

若最近可用摘要为 B，则新 Branch 不使用 B，而把 `active_summary_id` 指向 `B.parent_summary_id`。ContextBuilder 后续会自动补入父摘要覆盖终点至新 HEAD 之间的完整原文。

消息下方的左右箭头不是持久化字段。拥有相同 `parent_turn_id` 的多个 `completed` Turn 表示同一对话位置的不同版本；版本数大于 1 时，前端显示箭头。

### ✅ 完成的功能

- [x] 创建带根 Branch 的空会话。
- [x] 用户修改第 N 轮时，以第 N 轮的父 Turn 作为新 Branch HEAD。
- [x] 新 Branch 保存 `parent_branch_id` 和 `forked_from_turn_id`。
- [x] 创建新 Branch 后自动设为会话的活动分支。
- [x] 只允许重写 `completed` Turn。
- [x] 只允许重写位于来源 Branch 当前祖先链上的 Turn。
- [x] 来源 Branch 存在 pending Turn 时拒绝创建新分支，避免生成过程中的状态歧义。
- [x] 从来源 Branch 的活动摘要链向上查找不越过回退点的最近摘要，再额外退到其父摘要。
- [x] 回退到第一轮时，新 Branch HEAD 和活动摘要均为空。
- [x] 列出同一 `parent_turn_id` 下所有已完成消息版本。
- [x] 为每个消息版本返回一个可切换的代表 Branch。
- [x] 同一位置只有一个版本时，前端不显示箭头；存在多个版本时显示。
- [x] 切换版本只修改 `active_branch_id`，不删除或覆盖任何原文与摘要。

### ⚡ 暴露的函数/接口

#### `TurnVariant`

```python
@dataclass(frozen=True)
class TurnVariant:
    turn_id: str
    branch_id: str
    user_content: str
    created_at: datetime
    is_active: bool
```

输入来源：拥有相同 `parent_turn_id` 的已完成 Turn，以及包含该 Turn 的代表 Branch。

输出用途：前端显示当前版本序号、左右箭头，并在点击后把 `branch_id` 传给切换接口。

#### `BranchService`

```python
class BranchService:
    def __init__(self, repository: ConversationRepository) -> None: ...

    async def create_conversation(
        self,
        conversation_id: str,
    ) -> Conversation: ...

    async def create_branch_for_rewrite(
        self,
        conversation_id: str,
        source_branch_id: str,
        target_turn_id: str,
    ) -> Branch: ...

    async def list_turn_variants(
        self,
        conversation_id: str,
        target_turn_id: str,
    ) -> list[TurnVariant]: ...

    async def switch_branch(
        self,
        conversation_id: str,
        branch_id: str,
    ) -> Branch: ...
```

`create_conversation`：

- 输入：新的会话 ID。
- 输出：带一个空根 Branch 的 `Conversation`。
- 调用：用户第一次打开一个新对话窗口时调用一次。

`create_branch_for_rewrite`：

- 输入：会话 ID、当前来源 Branch、用户准备修改的旧 `turn_id`。
- 输出：新创建并设为活动状态的 `Branch`。
- 注意：本方法只建立分支，不保存修改后的新用户内容；新内容由下一阶段的 ChatService 作为 pending Turn 写入。

`list_turn_variants`：

- 输入：当前界面某条用户消息对应的 `turn_id`。
- 输出：按创建时间排序的同位置消息版本。
- 前端通过 `len(variants) > 1` 决定是否显示箭头。

`switch_branch`：

- 输入：会话 ID与版本结果携带的 `branch_id`。
- 输出：切换后的活动 Branch。
- 修改范围：只更新 `Conversation.active_branch_id`。

验证方式：

1. 新建会话，确认只包含一个空根 Branch。
2. 在三轮历史中重写第三轮，确认新 HEAD 为第二轮，旧第三轮仍保留。
3. 摘要 B 的父摘要为 A 时重写 B 之后的轮次，确认新分支使用 A。
4. 回退点早于 B 时，确认先沿摘要父链找到可用摘要，再向上多退一层。
5. 重写第一轮，确认新分支从空 HEAD 开始。
6. 完成新版本后查询原 Turn，确认返回两个兄弟版本并显示不同 Branch。
7. 切换版本，确认原文、分支 HEAD 和摘要内容均未改变。
