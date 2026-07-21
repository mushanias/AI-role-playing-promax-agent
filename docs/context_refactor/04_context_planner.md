# 上下文与压缩机制重构交付文档（04）

## 模块名称：分支 Context 规划

### 📦 输出

- `app/models/context_plan.py`：新增语义化 Context 计划和候选结果。
- `app/models/__init__.py`：导出 Context 计划模型。
- `app/services/context_planner.py`：新增当前分支历史解析与水位判断。
- `app/services/context_builder.py`：保留旧接口，同时增加根据 `ContextPlan` 生成真实 LLM messages 的接口。
- `app/services/__init__.py`：导出 `ContextPlanner`。
- `app/core/config.py`：增加高水位、低水位和近期原文目标配置。
- `test/test_context_planner.py`：验证分支隔离、摘要边界、pending 轮次和水位结果。

### 🧩 解决的问题

现有 `ContextBuilder` 接收线性消息列表，并依赖单个 `compressed_until_message_id` 截取历史。新架构中，Context 必须只沿当前 Branch 的 HEAD 父链读取，不能混入其他剧情结局。

本模块把流程拆为两步：

```text
ContextPlanner
→ 决定使用哪份活动摘要、哪些完整原文、哪个 pending Turn

ContextBuilder
→ 把计划转换为真正发送给 LLM 的 messages，并用相同内容计算 Token
```

这样水位判断和最终请求不会使用两套不同的计算口径。

### ✅ 完成的功能

- [x] 从指定 Branch 的 `head_turn_id` 沿 `parent_turn_id` 回溯到根。
- [x] 反转父链，得到按时间正序排列的完整历史。
- [x] 只读取当前剧情路径，不混入其他兄弟 Turn。
- [x] 有活动摘要时，从 `covered_until_turn_id` 的下一轮开始保留原文。
- [x] 无活动摘要时，保留当前分支从根开始的全部原文。
- [x] 活动摘要覆盖到 HEAD 时，未覆盖原文可以为空。
- [x] `pending_turn_id` 指向的用户输入追加在 messages 最后。
- [x] pending Turn 可进入本轮 Context，但不进入 `raw_turns` 压缩候选。
- [x] 全局 `profile.json` 设定放在 system 内容最前面。
- [x] 活动摘要紧随全局设定写入 system 内容。
- [x] 每个完整 Turn 固定展开为一条 user message 和一条 assistant message。
- [x] 使用最终 messages 执行 Token 估算。
- [x] ContextBuilder 只依赖最小 Token 计算 Protocol；生产可用 `TokenCounter`，测试可注入轻量替身。
- [x] 总量超过高水位时标记 `needs_compression=True`。
- [x] 候选结果携带低水位和近期原文目标，供下一压缩模块使用。
- [x] 保留旧 `ContextBuilder.build` 接口，完成最终切换前不破坏现有聊天流程。

MVP 默认质量参数：

```text
高水位：40000 Token
压缩后低水位：25000 Token
近期原文目标：10000 Token
```

三个值只表示应用质量策略；模型硬上限和超长降级将在后续聊天编排模块处理。

### ⚡ 暴露的函数/接口

#### `ContextPlan`

```python
@dataclass(frozen=True)
class ContextPlan:
    conversation_id: str
    branch_id: str
    summary: SummaryVersion | None
    raw_turns: tuple[Turn, ...]
    pending_turn: Turn | None
```

输入来源：已经通过校验的 `Conversation` 与目标 Branch。

输出：不包含 JSON、Token 或 LLM 调用细节的语义化 Context 选择结果。

#### `ContextCandidate`

```python
@dataclass(frozen=True)
class ContextCandidate:
    plan: ContextPlan
    messages: tuple[dict[str, str], ...]
    estimated_tokens: int
    high_watermark: int
    low_watermark: int
    recent_raw_token_target: int
    needs_compression: bool
```

输出用途：ContextManager 根据 `needs_compression` 决定直接调用聊天 LLM，还是先进入同步压缩流程。

#### `ContextPlanner`

```python
class ContextPlanner:
    def __init__(
        self,
        context_builder: ContextBuilder,
        high_watermark: int,
        low_watermark: int,
        recent_raw_token_target: int,
    ) -> None: ...

    def build_candidate(
        self,
        conversation: Conversation,
        profile: dict[str, str],
        branch_id: str | None = None,
    ) -> ContextCandidate: ...
```

- `branch_id=None` 时使用 `Conversation.active_branch_id`。
- 输入为内存模型，不在 Planner 内部读取或写入 JSON。
- 输出为本轮完整候选 Context 和水位判断。

#### `ContextBuilder.build_from_plan`

```python
def build_from_plan(
    self,
    profile: dict[str, str],
    plan: ContextPlan,
) -> PlannedContextBuildResult: ...
```

输入：全局设定和 Context 语义计划。

输出：最终 messages 与对应 Token 估算。

验证方式：

1. 主线与分支各自拥有独立后续 Turn，确认候选 Context 只包含目标分支路径。
2. 摘要覆盖到第二轮，确认只发送摘要和第三轮之后的原文。
3. 活动摘要为空，确认发送从根到 HEAD 的全部原文。
4. Branch 存在 pending Turn，确认其用户内容位于最后且不进入 `raw_turns`。
5. 分别构造高于和低于高水位的候选，确认 `needs_compression` 正确。
