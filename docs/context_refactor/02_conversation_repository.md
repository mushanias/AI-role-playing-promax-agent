# 上下文与压缩机制重构交付文档（02）

## 模块名称：会话 JSON 仓库

### 📦 输出

- `app/storage/conversation_repository.py`：新增单会话 JSON 仓库。
- `app/storage/__init__.py`：导出 `ConversationRepository`。
- `app/exceptions/storage_errors.py`：增加“会话不存在”和“会话已存在”异常。
- `app/exceptions/__init__.py`：统一导出新增异常。
- `app/core/config.py`：增加会话目录配置 `CONVERSATIONS_PATH`。
- `test/test_conversation_repository.py`：验证创建、加载、保存、更新、损坏文件与并发保护。

每个会话持久化为：

```text
data/conversations/{conversation_id}.json
```

本模块复用现有 `JsonFileStore` 的临时文件写入与 `os.replace` 原子替换能力，不修改用户已有的 JSON 文件读写实现。

### 🧩 解决的问题

现有 `JsonStorage` 只支持向一个线性消息数组追加消息，无法一次保存 Turn、Branch 和 Summary 之间的多个关联指针。

新仓库以完整 `Conversation` 为读写单位，保证一次业务变更中的“新增记录 + 移动指针”写入同一个 JSON 文件。仓库只负责持久化和模型校验，不决定如何创建分支、选择摘要或压缩历史。

仓库为每个 `conversation_id` 使用独立异步锁，避免同一进程中的两个请求同时执行“读取旧值—分别写回”而互相覆盖。不同会话仍可并行读写。

### ✅ 完成的功能

- [x] 一个会话对应一个 JSON 文件。
- [x] 创建新会话时拒绝覆盖已存在文件。
- [x] 加载不存在的会话时返回明确的存储异常。
- [x] JSON 解析失败、根结构错误或模型引用非法时统一视为存储损坏。
- [x] 保存前重新执行完整 `Conversation` 模型校验。
- [x] 使用 `model_dump(mode="json")` 正确序列化 UUID 字符串、枚举和时间。
- [x] `update` 在单会话锁内完成加载、变更、校验和原子保存。
- [x] 更新函数只接收和返回 `Conversation`，仓库不理解具体业务动作。
- [x] 不暴露删除接口，避免误删不可变历史。
- [x] 限制 `conversation_id` 只能包含字母、数字、下划线和连字符，防止路径逃逸。
- [x] 不修改现有 `chat_history.json`，旧聊天流程在接入新服务前仍可运行。

### ⚡ 暴露的函数/接口

#### `ConversationRepository`

```python
class ConversationRepository:
    def __init__(self, base_directory: str) -> None: ...

    async def exists(self, conversation_id: str) -> bool: ...

    async def create(self, conversation: Conversation) -> None: ...

    async def load(self, conversation_id: str) -> Conversation: ...

    async def save(self, conversation: Conversation) -> None: ...

    async def update(
        self,
        conversation_id: str,
        updater: Callable[[Conversation], Conversation],
    ) -> Conversation: ...
```

`exists`：

- 输入：`conversation_id`。
- 输出：对应 JSON 文件是否存在。

`create`：

- 输入：已经包含根 Branch 的合法 `Conversation`。
- 输出：无；成功后创建新 JSON 文件。
- 已存在同名文件时抛出 `StorageConflictError`。

`load`：

- 输入：`conversation_id`。
- 输出：通过完整校验的 `Conversation`。
- 文件不存在时抛出 `StorageNotFoundError`。

`save`：

- 输入：完整 `Conversation` 快照。
- 输出：无。
- 仅替换已经存在的会话；主要供迁移或明确的整份保存使用。

`update`：

- 输入：会话 ID，以及一个同步的状态变更函数。
- 输出：写入成功后的新 `Conversation` 快照。
- 调用方不能在 updater 中执行 LLM 或文件 I/O；它只描述一次快速的内存状态变化。

调用示意：

```python
def move_head(conversation: Conversation) -> Conversation:
    conversation.branches[branch_id].head_turn_id = new_turn_id
    return conversation

updated = await repository.update(conversation_id, move_head)
```

验证方式：

1. 创建会话并检查 `{conversation_id}.json` 文件存在。
2. 加载会话并确认时间、状态枚举和所有指针正确恢复。
3. 重复创建同一 ID，确认不会覆盖原文件。
4. 加载不存在的 ID，确认返回 `StorageNotFoundError`。
5. 手工写入非法 JSON 或断裂指针，确认返回 `StorageCorruptionError`。
6. 使用两个并发 `update`，确认第二次更新能够看到第一次更新结果，不发生丢失更新。
