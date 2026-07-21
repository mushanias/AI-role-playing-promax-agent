# 上下文与压缩机制重构交付文档（01）

## 模块名称：会话历史数据模型

### 📦 输出

- `app/models/conversation.py`：新增会话聚合模型，统一定义原始轮次、剧情分支、摘要版本和会话根对象。
- `app/models/context_state.py`：后续由新模型取代；本模块确认其现有 `summary + compressed_until_message_id` 结构不再作为新架构的数据源。
- `data/conversations/{conversation_id}.json`：每个会话一个 JSON 文档；具体读写由下一模块负责。

建议的 JSON 根结构：

```json
{
  "schema_version": 1,
  "conversation_id": "conv-uuid",
  "active_branch_id": "branch-uuid",
  "turns": {},
  "branches": {},
  "summaries": {}
}
```

全局开局设定不进入此文件，继续保存于：

```text
data/profile.json
```

后续剧情中的新增设定作为用户对话原文保存，不生成独立的设定版本链。

### 🧩 解决的问题

现有历史使用独立消息列表，并通过单个 `message_id` 标记压缩边界，存在以下限制：

- 无法保证压缩边界落在完整的“用户输入 + 助手回复”轮次上；
- 无法表达用户从旧轮次重写剧情后产生的多条结局链；
- 摘要被覆盖保存，无法退回父摘要并恢复最近一层原文；
- 失败或未完成的用户轮次缺少明确状态；
- 原文位置、当前分支和活动摘要混在同一个线性状态中。

新模型把数据拆成三类：

```text
Turn       = 永久保存的原始剧情轮次
Branch     = 当前剧情线的书签
Summary    = 可替换使用、但不可覆盖删除的历史笔记
```

用户修改第 N 轮时，新分支保留第 1 至 N-1 轮；旧第 N 轮仍留在旧分支，不删除、不覆盖。

MVP 界面中的 `turn_id` 同时作为用户点击和编辑的目标。用户修改某条用户消息时，系统不会改写原 Turn，而是在同一个 `parent_turn_id` 下创建新的 Turn 和 Branch：

```text
原版本：Turn 1 → Turn 2 → Turn 3
新版本：Turn 1 → Turn 2 → Turn 3'
```

第一次发送时，该位置只有一个版本，不显示切换箭头；发生修改并产生两个及以上同位置版本后，界面才显示左右箭头。箭头状态不需要额外持久化，可根据拥有相同 `parent_turn_id` 的兄弟 Turn 动态计算。

### ✅ 完成的功能

- [x] 原始历史按完整 `turn_id` 轮次建模，不再按单条消息作为压缩单位。
- [x] 每个 Turn 同时保存用户原文和助手原文。
- [x] Turn 支持 `pending`、`completed`、`failed` 三种状态。
- [x] `pending` Turn 可进入当前请求 Context，但不得进入摘要压缩。
- [x] 只有 `completed` Turn 可以推进分支的 `head_turn_id`。
- [x] 已进入 `completed` 或 `failed` 状态的 Turn 不再修改或删除。
- [x] Turn 使用 UUID 字符串作为身份，不依赖连续数字，因此 ID 跳跃不影响历史关系。
- [x] 每个 Turn 通过 `parent_turn_id` 指向上一完整轮次；回退产生分支后，整体形成有向无环图。
- [x] Branch 单独保存当前原文指针 `head_turn_id` 和活动摘要指针 `active_summary_id`。
- [x] Branch 保存 `parent_branch_id` 与 `forked_from_turn_id`，用于表达剧情线来源。
- [x] Summary 追加保存，通过 `parent_summary_id` 形成摘要版本链。
- [x] Summary 通过 `covered_until_turn_id` 指向它覆盖到的最后一个完整原文轮次。
- [x] 创建新分支时，活动摘要指针向父摘要移动一层；Builder 随后读取父摘要覆盖点到新 HEAD 之间的原文。
- [x] 不在 Turn 中强制保存 `branch_id`；共同前缀的 Turn 可以被多条分支共享。
- [x] `turn_id` 可直接作为界面编辑目标；编辑旧用户消息时创建兄弟 Turn，不覆盖原 Turn。
- [x] 同一位置的版本切换箭头由兄弟 Turn 数量动态决定，不额外保存易失的 UI 状态。
- [x] 最终发送给 LLM 的 `messages` 不持久化，后续由 Context 模块按需重新组装。
- [x] 第一版不引入数据库、向量库或检索索引。

必须保持的引用约束：

1. `Turn.parent_turn_id` 必须为空或指向已存在的 Turn。
2. `Branch.head_turn_id` 必须为空或指向当前分支路径上的 `completed` Turn。
3. `Branch.pending_turn_id` 必须为空或指向 `pending` Turn。
4. `Branch.active_summary_id` 必须为空或指向已存在的 Summary。
5. 活动 Summary 的 `covered_until_turn_id` 必须位于该 Branch 的 HEAD 祖先链上。
6. `Summary.parent_summary_id` 必须为空或指向覆盖范围更早的 Summary。
7. 原文轮次和摘要版本只追加；分支指针允许移动。

### ⚡ 暴露的函数/接口

#### `TurnStatus`

```python
class TurnStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
```

#### `Turn`

```python
class Turn(BaseModel):
    turn_id: str
    parent_turn_id: str | None
    user_content: str
    assistant_content: str | None
    status: TurnStatus
    created_at: datetime
    completed_at: datetime | None
    failure_message: str | None
```

输入：一次用户输入，以及它所属历史位置的 `parent_turn_id`。

输出：可持久化的完整轮次记录。`assistant_content` 在 `pending` 状态可以为空；进入 `completed` 后必须存在。

#### `SummaryVersion`

```python
class SummaryVersion(BaseModel):
    summary_id: str
    parent_summary_id: str | None
    covered_until_turn_id: str
    content: str
    created_at: datetime
```

输入：父摘要、连续完整轮次的压缩结果及覆盖终点。

输出：不可覆盖修改的摘要版本。

#### `Branch`

```python
class Branch(BaseModel):
    branch_id: str
    parent_branch_id: str | None
    forked_from_turn_id: str | None
    head_turn_id: str | None
    pending_turn_id: str | None
    active_summary_id: str | None
    created_at: datetime
```

输入：分支来源、保留到的原文轮次以及允许复用的摘要层。

输出：当前剧情线的持久化书签。

MVP 中“修改第 N 轮”的固定语义：

```text
新 Branch.head_turn_id = 旧第 N 轮的 parent_turn_id
新 Branch.active_summary_id = 最近可用摘要的 parent_summary_id
```

#### `Conversation`

```python
class Conversation(BaseModel):
    schema_version: int = 1
    conversation_id: str
    active_branch_id: str
    turns: dict[str, Turn]
    branches: dict[str, Branch]
    summaries: dict[str, SummaryVersion]
```

输入：单个会话 JSON 解码后的字典。

输出：通过字段类型和引用约束校验的会话对象。

调用位置：下一模块的 `ConversationRepository` 负责从 JSON 加载并构造此对象；`ChatService`、`BranchService` 和 `ContextManager` 只接收模型对象，不直接解析 JSON 字典。

验证方式：

1. 创建根分支，确认空 `head_turn_id` 和空摘要合法。
2. 创建 `pending` Turn，确认它可以被 `pending_turn_id` 引用但不能成为 HEAD。
3. 完成 Turn 后推进 HEAD，确认父链能够从 HEAD 回溯到根。
4. 从第 N 轮创建新分支，确认新 HEAD 等于旧第 N 轮的父轮次，旧第 N 轮仍可从旧分支访问。
5. 创建父子摘要 A、B，确认新分支可把活动摘要从 B 移到 A，并读取 A 覆盖点之后到 HEAD 的完整原文。
6. 构造不存在的父 Turn、错误状态的 pending 指针或不属于当前祖先链的摘要，确认模型校验失败。
