# 上下文与压缩机制重构交付文档（05）

## 模块名称：追加式同步压缩

### 📦 输出

- `app/models/compression_plan.py`：新增完整 Turn 压缩计划与执行结果模型。
- `app/models/__init__.py`：导出压缩计划模型。
- `app/services/versioned_context_compression_service.py`：新增批次选择和追加式摘要压缩服务。
- `app/services/__init__.py`：导出新版压缩服务。
- `test/test_versioned_context_compression.py`：验证完整轮次边界、近期原文软目标、摘要父链、分支隔离和并发状态变化。

旧 `ContextCompressionService` 暂时保留，直到新 ChatService 完成接线。

### 🧩 解决的问题

现有压缩按消息数量截取，并覆盖单一 `ContextState.summary`。新压缩必须做到：

```text
旧活动摘要 + 较早的完整 Turn
→ 新 SummaryVersion
→ 当前 Branch.active_summary_id 指向新版本
```

原始 Turn、旧 Summary 和其他 Branch 均不修改。

压缩 LLM 调用期间不能长期锁住会话 JSON。本模块先记录规划时的 HEAD、pending 和活动摘要指针，LLM 返回后再在仓库锁内校验这些指针；若状态已经变化，则丢弃过期结果，不污染当前历史。

### ✅ 完成的功能

- [x] 仅在 `ContextCandidate.needs_compression=True` 时规划压缩。
- [x] 只从 `raw_turns` 的最早端选择连续完整 Turn。
- [x] pending Turn 永远不进入压缩批次。
- [x] 遍历完整 Turn 边界，寻找压缩后可达到 25k 低水位的切点。
- [x] 在可行切点中选择剩余原文最接近 10k 目标的一项。
- [x] 单个 Turn 超过 10k 时保持完整，不从中间截断。
- [x] 根据设定、pending、剩余原文和安全余量动态计算摘要 Token 上限。
- [x] 新摘要的 `parent_summary_id` 等于规划时的活动摘要。
- [x] 新摘要的 `covered_until_turn_id` 等于压缩批次最后一个 Turn。
- [x] 新 SummaryVersion 追加保存，不覆盖父摘要。
- [x] 仅更新目标 Branch 的活动摘要指针。
- [x] 压缩完成后重新构建真实 ContextCandidate，使用实际摘要长度复核水位。
- [x] 无可压缩完整轮次或固定内容已挤满低水位时返回 warning，不抛 `ContextBudgetError`。
- [x] LLM 调用期间 HEAD、pending 或活动摘要变化时丢弃过期摘要结果。

### ⚡ 暴露的函数/接口

#### `VersionedCompressionPlan`

```python
@dataclass(frozen=True)
class VersionedCompressionPlan:
    conversation_id: str
    branch_id: str
    expected_head_turn_id: str | None
    expected_pending_turn_id: str | None
    expected_active_summary_id: str | None
    old_summary: str
    turns_to_compress: tuple[Turn, ...]
    raw_turns_to_keep: tuple[Turn, ...]
    summary_token_budget: int
    estimated_result_upper_bound: int
```

#### `VersionedCompressionOutcome`

```python
@dataclass(frozen=True)
class VersionedCompressionOutcome:
    candidate: ContextCandidate
    summary: SummaryVersion | None
    compressed: bool
    stale: bool
    warning: str | None
```

调用方始终得到可继续处理的候选 Context；无法压缩时通过 `warning` 通知界面，不使用预算异常中断对话。

#### `CompressionBatchPlanner`

```python
class CompressionBatchPlanner:
    def plan(
        self,
        candidate: ContextCandidate,
        profile: dict[str, str],
    ) -> VersionedCompressionPlan | None: ...
```

输入：当前真实候选 Context 和全局设定。

输出：完整 Turn 压缩计划；无法在保留摘要空间的前提下达到低水位时返回 `None`。

#### `VersionedContextCompressionService`

```python
class VersionedContextCompressionService:
    async def compress_if_needed(
        self,
        conversation_id: str,
        branch_id: str,
        profile: dict[str, str],
    ) -> VersionedCompressionOutcome: ...
```

执行流程：

```text
加载会话
→ ContextPlanner 生成候选
→ CompressionBatchPlanner 选择完整 Turn
→ Compressor 调用摘要 LLM
→ 仓库锁内校验旧指针
→ 追加 SummaryVersion 并更新 Branch 指针
→ 重新生成候选 Context
```

验证方式：

1. 构造超过高水位的多轮历史，确认批次结束在完整 Turn。
2. 确认未压缩尾部 Token 最接近近期原文目标。
3. 存在旧摘要 A 时压缩新原文，确认生成摘要 B 且 `B.parent_summary_id=A`。
4. 确认 A 和所有原始 Turn 仍存在且内容未变。
5. 压缩 LLM 返回前推进 HEAD，确认结果标记 stale 且不写入摘要。
6. 只有 pending 或单个不可切分 Turn 导致超水位时，确认返回 warning 而非预算异常。
