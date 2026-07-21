# 上下文与压缩机制重构交付文档（06）

## 模块名称：分支化 ContextManager 编排

### 📦 输出

- `app/models/context_plan.py`：新增最终 Context 编排结果 `ManagedContext`。
- `app/models/__init__.py`：导出 `ManagedContext`。
- `app/services/versioned_context_manager.py`：新增按会话分支工作的 ContextManager。
- `app/services/__init__.py`：导出 `VersionedContextManager`。
- `test/test_versioned_context_manager.py`：验证同步压缩循环、警告降级和分支选择。

旧 `ContextManager` 暂时保留，避免尚未改造的 `ChatService` 和依赖注入提前断开。最终接线完成后再统一移除旧链路。

### 🧩 解决的问题

前五个模块已经能够保存分支、规划 Context 和生成版本化摘要，但还缺少主对话调用前的统一编排入口。本模块把它们串成下面的同步流程：

```text
读取一次全局设定
→ 加载指定会话与分支
→ 构建真实 ContextCandidate
→ 超过 40k 高水位时同步压缩
→ 使用实际新摘要重新估算
→ 必要时继续压缩，最多执行配置的次数
→ 返回 messages、压缩次数与 warnings
```

无法继续压缩或达到最大压缩次数时，不再抛出 `ContextBudgetError`。调用方仍然取得 Context，同时通过 `warnings` 通知界面展示“输入过长、当前质量可能下降”。

### ✅ 完成的功能

- [x] 使用 `conversation_id` 和可选 `branch_id` 选择剧情链路。
- [x] 未指定 `branch_id` 时复用会话的活动分支。
- [x] 每次构建只读取一次全局设定。
- [x] 未超过质量高水位时不调用压缩 LLM。
- [x] 超过高水位时在主对话 LLM 调用前同步压缩。
- [x] 每次压缩后使用实际摘要结果重新判断水位。
- [x] 实际摘要仍然过长时允许继续压缩，次数受 `max_compression_passes` 限制。
- [x] 压缩服务无法安全压缩时立即停止，避免重复消耗 LLM。
- [x] 汇总压缩服务产生的 warning，并去除重复文本。
- [x] 达到最大压缩次数后仍超水位时追加降级 warning。
- [x] 极端超长场景始终返回 `ManagedContext`，不抛预算异常。
- [x] 返回的消息仍由 `ContextPlanner` 决定，保持摘要、近期原文和 pending Turn 的正确顺序。

### ⚡ 暴露的函数/接口

#### `ManagedContext`

```python
@dataclass(frozen=True)
class ManagedContext:
    candidate: ContextCandidate
    warnings: tuple[str, ...]
    compression_passes: int

    @property
    def messages(self) -> tuple[dict[str, str], ...]: ...

    @property
    def quality_degraded(self) -> bool: ...
```

输入：由 `VersionedContextManager` 完成编排后创建。

输出：最终候选 Context、界面警告和本轮实际压缩尝试次数。`messages` 可直接交给主对话 LLM；`quality_degraded` 用于 API 或界面判断是否显示质量提示。

#### `VersionedContextManager`

```python
class VersionedContextManager:
    async def build(
        self,
        conversation_id: str,
        branch_id: str | None = None,
    ) -> ManagedContext: ...
```

调用方式：聊天编排层在 pending Turn 已经写入会话后调用 `build()`，再把 `result.messages` 发送给主对话 LLM。

验证方式：

1. 构造低于高水位的分支，确认不触发压缩。
2. 构造超过高水位的分支，确认先压缩再返回新 Context。
3. 模拟第一次压缩后仍超水位，确认继续执行第二次压缩。
4. 模拟无法压缩和最大次数耗尽，确认返回 warning 而不是 `ContextBudgetError`。
5. 不传 `branch_id`，确认使用活动分支；显式传入时确认使用目标分支。
