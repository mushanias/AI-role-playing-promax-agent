# 版本化会话引擎设计

## 历史结构

Turn 使用 `parent_turn_id` 保存父指针。Branch 使用 `head_turn_id`
选择一条历史路径。读取时从 HEAD 沿父指针回溯到根，再反转为时间正序。

```text
          T3
         /
T1 → T2
         \
          T3' → T4'
```

选择 `T3` 和选择 `T4'` 会得到不同历史，但两条分支共享 `T1、T2`。

## 消息重写

重写目标 Turn 时：

1. 验证目标 Turn 位于来源分支的祖先链。
2. 取目标 Turn 的 `parent_turn_id` 作为新分支 HEAD。
3. 创建新 Branch 并切换为活动分支。
4. 将修改后的用户输入保存为新的 pending Turn。
5. LLM 成功后完成 Turn 并推进新分支 HEAD。

旧 Turn、旧 Branch 和旧摘要均不覆盖。

## 摘要版本

压缩只选择尚未被活动摘要覆盖的连续 completed Turn。每次压缩创建新的
`SummaryVersion`，并把 Branch 的 `active_summary_id` 移到新摘要。

重写较早消息时，摘要指针会沿父摘要链回退，使新分支恢复靠近分叉位置的
原始细节，避免使用覆盖范围越过回退点的摘要。

## 并发保护

压缩 LLM 调用前记录：

```text
expected_head_turn_id
expected_pending_turn_id
expected_active_summary_id
```

写入摘要前重新检查三项指针。任意一项发生变化，说明压缩结果基于过期
Context，结果会被丢弃。

## 降级原则

无法安全压缩时，系统只调整本次发送给主 LLM 的副本：

1. 逐步省略较早原文。
2. 必要时省略活动摘要。
3. 当前输入仍超限时保留首尾并加入截断标记。

持久化的 Turn 和 SummaryVersion 不受影响。
