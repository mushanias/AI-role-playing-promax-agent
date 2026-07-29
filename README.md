# 角色扮演 Agent：上下文与压缩机制

本文只描述当前后端 MVP 已经实现的上下文处理、剧情分支和历史压缩机制。

## 1. 核心原则

- **原始历史不删除**：正常业务流程不会删除旧 Turn、旧分支或旧摘要。
- **按完整 Turn 处理**：一个 Turn 由一次用户输入及其对应的助手回复组成；常规压缩不会从中间切断 Turn。
- **当前输入可以进入 Context，但不能进入压缩**：正在生成的用户输入是 `pending` Turn，只发送给主对话 LLM，不参与本轮摘要。
- **摘要只替代发送，不替代存储**：被摘要覆盖的原文不再重复发送给 LLM，但仍完整保存在 JSON 中。
- **分支各自持有上下文指针**：每条剧情分支都有自己的 HEAD 和活动摘要，不会因为另一条分支继续发展而丢失。
- **超长时优先继续对话**：无法安全压缩时返回 warning，并只缩减本次发送副本；持久化原文不受影响。

## 2. 数据存放位置

```text
data/
├── profile.json
└── conversations/
    └── {conversation_id}.json
```

`profile.json` 保存一份全局开局设定，每次请求都会动态注入。开局以后新增的世界观、人物关系或剧情设定，作为普通用户对话进入 Turn 历史。

每个会话使用一个独立 JSON 文件，其中四组关键数据是：

| 字段 | 作用 |
| --- | --- |
| `turns` | 保存所有原始轮次，包括旧分支中的轮次和失败的轮次 |
| `branches` | 保存各剧情分支的 HEAD、pending Turn 和活动摘要指针 |
| `summaries` | 保存所有追加生成的摘要版本 |
| `active_branch_id` | 指向界面当前选中的剧情分支 |

当前使用 UUID 作为 `turn_id`、`branch_id` 和 `summary_id`。UUID 是否连续并不重要，真正的历史顺序由父指针决定。

## 3. 完整 Turn 与历史链

一个 Turn 的数据含义如下：

```text
Turn
├── turn_id
├── parent_turn_id       指向上一轮
├── user_content         用户原文
├── assistant_content    助手原文
└── status               pending / completed / failed
```

历史不是依赖数组下标排列，而是通过 `parent_turn_id` 串成单父链：

```text
T1 <- T2 <- T3 <- T4
                  ↑
              Branch HEAD
```

构建某条分支的上下文时，系统从该分支的 HEAD 沿父指针回溯到根，再反转成 `T1 → T2 → T3 → T4`。因此即使 ID 看起来跳跃，也不会影响顺序和回退。

Turn 的状态变化是：

```text
收到用户输入
→ 创建 pending Turn
→ 构建 Context 并调用 LLM
→ 成功：补入助手回复，改为 completed，并推进 Branch HEAD
→ 失败：改为 failed，Branch HEAD 保持不变
```

`pending` Turn 只有用户输入，可以进入本轮 Context；只有 `completed` Turn 才能成为历史链节点并参与摘要。失败 Turn 仍保存在 `turns` 中，但不会推进当前剧情线。

## 4. 发给主对话 LLM 的 Context

当前 Context 固定按以下顺序组装：

```text
1. 全局开局设定 profile
2. 当前分支的活动摘要（如果存在）
3. 活动摘要尚未覆盖的近期完整原文 Turn
4. 本轮 pending 用户输入
```

最终转换为 LLM messages 时：

- 全局设定与活动摘要合并为一条 `system` message；
- 每个近期完整 Turn 展开为一条 `user` 和一条 `assistant` message；
- pending Turn 只展开为最后一条 `user` message。

例如，摘要 `S1` 已覆盖到 `T3`，分支 HEAD 是 `T6`，当前输入是 `T7`：

```text
system:    profile + S1
user:      T4.user
assistant: T4.assistant
user:      T5.user
assistant: T5.assistant
user:      T6.user
assistant: T6.assistant
user:      T7.user          ← pending，只参与对话，不参与压缩
```

系统只发送当前活动摘要，不会把整条旧摘要链重复发送。活动摘要本身已经吸收了父摘要中的信息。

## 5. 水位配置

当前默认配置：

```dotenv
CONTEXT_HIGH_WATERMARK=40000
CONTEXT_LOW_WATERMARK=25000
RECENT_RAW_TOKEN_TARGET=10000
CONTEXT_SAFETY_MARGIN=200
SUMMARY_TOKEN_BUDGET=1000
MAX_COMPRESSION_PASSES=3
```

它们分别表示：

| 配置 | 当前含义 |
| --- | --- |
| `40000` 高水位 | 完整候选 Context 超过该值才触发同步压缩 |
| `25000` 低水位 | 压缩后 Context 的软目标上限，为后续对话预留增长空间 |
| `10000` 近期原文目标 | 在可行的完整 Turn 切点中，尽量保留约 10k 原文 |
| `200` 安全余量 | 为估算误差预留空间 |
| `1000` 最小摘要预算 | 如果连最小摘要空间都无法留出，则认为该切点不可用 |
| `3` 最大压缩次数 | 一次主对话请求前最多连续压缩三次 |

水位判断针对**实际组装后的整份 messages**，包含全局设定、活动摘要、近期原文和当前 pending 输入，而不是只计算历史原文。

## 6. 压缩批次如何选择

只有 Context 严格超过 40k 高水位才压缩。压缩规划器从“尚未被活动摘要覆盖的原文”开头选择连续完整 Turn：

```text
旧活动摘要 + 较早的完整原文 Turn
→ 新摘要

较新的完整原文 Turn
→ 继续保留原文发送
```

规划器会依次尝试每个完整 Turn 切点，并执行以下判断：

1. 计算保留全局设定、近期原文和 pending 输入后还剩多少空间。
2. 确认新摘要至少拥有 `SUMMARY_TOKEN_BUDGET` 的空间。
3. 确认“固定内容 + 新摘要预算 + 安全余量”不超过 25k 低水位。
4. 在所有可行切点中，选择让近期原文最接近 10k 的一个；距离相同时保留更多原文。

因此 10k 是软目标，不是硬切割线。若一个 Turn 本身跨过 10k 边界，系统会完整保留或完整压缩它，不会拆开用户输入和助手回复。

## 7. 追加式摘要版本

每次压缩都会创建新的 `SummaryVersion`：

```text
S1 <- S2 <- S3
            ↑
    Branch.active_summary_id
```

每个摘要包含：

- `summary_id`：摘要自身 ID；
- `parent_summary_id`：压缩前使用的活动摘要；
- `covered_until_turn_id`：该摘要覆盖到的最后一个原始 Turn；
- `content`：摘要正文；
- `created_at`：创建时间。

生成 `S2` 时，压缩 LLM 接收 `S1.content + 新选中的较早原文`。成功后系统追加保存 `S2`，再把当前分支的 `active_summary_id` 从 `S1` 移到 `S2`。`S1` 和所有被覆盖原文仍然保留。

压缩完成后，系统使用真实的新摘要重新构建并估算 Context；若仍超过高水位，可以继续下一次压缩，最多执行配置的次数。

## 8. 修改旧消息与“摘要隔一轮”

修改第 N 轮不是覆盖原 Turn，而是：

1. 保留到第 N-1 轮；
2. 创建一条新 Branch；
3. 在新 Branch 上把修改后的内容创建为新 Turn；
4. 旧 Branch、旧 Turn 和旧摘要全部保留，可再次切换回来。

创建新分支时，系统先寻找“回退位置本来可以使用的最新摘要”，然后把活动摘要指针再向父摘要退一层。这就是当前实现的**摘要隔一轮**。

例如：

```text
S1 覆盖 T1~T3
S2 覆盖 T1~T6
当前剧情已经发展到 T9
```

如果修改 `T8`，新分支保留到 `T7`。`S2` 虽然覆盖终点 `T6`，理论上可以使用，但新分支会主动退到 `S1`：

```text
新分支 Context = S1 + T4 + T5 + T6 + T7 + 修改后的 T8
```

如果修改 `T4`，新分支只保留到 `T3`。即使 `S1` 正好覆盖到 `T3`，本轮也不直接使用 `S1`，而是发送 `T1~T3` 原文：

```text
新分支 Context = T1 + T2 + T3 + 修改后的 T4
```

这样做的目的，是在剧情刚分叉时恢复靠近分叉点的原始细节，同时仍允许复用更早、更稳定的摘要。新分支后续只有再次超过高水位，才会生成属于该分支的新摘要。

## 9. 并发压缩保护

压缩 LLM 调用可能持续较长时间，因此调用期间不会一直锁住会话文件。系统会在调用前记录：

- Branch HEAD；
- pending Turn；
- active summary。

摘要返回后，系统在写入锁内再次检查这三个指针。若其中任何一个已经变化，说明该摘要基于过期历史生成；结果会被丢弃并返回 warning，不会写入当前剧情线。

同一进程内，每个会话还有独立的异步锁，JSON 使用“临时文件写入、刷新、原子替换”的方式保存。当前 MVP 应使用单个服务进程；进程间共享 JSON 时没有跨进程锁保护。

## 10. 极端超长时的降级

如果 Context 超过高水位，但没有可安全压缩的完整 Turn，或达到最大压缩次数后仍然过长，系统不会抛出 Context 预算错误，而是仅调整本次发送给主 LLM 的副本：

1. 依次省略最早的完整原文 Turn；
2. 仍然过长时省略活动摘要；
3. 若全局设定或当前输入本身就超过限制，临时保留内容首尾并加入截断标记。

这个降级副本不会回写 JSON。原始 Turn、摘要和全局设定仍完整保存，API 成功响应通过 `warnings` 和 `quality_degraded` 告知前端本轮效果可能下降。

## 11. 当前 MVP 边界

- 使用 JSON 持久化，不使用数据库或向量库。
- 摘要按剧情时间顺序压缩，不做语义检索和长期记忆召回。
- 全局开局设定只有一份；后续设定变化保存在对话原文中。
- JSON 并发保护只覆盖单个 Python 进程。
- Context 数值是质量水位，不代表模型供应商的绝对输入上限。

## 12. 项目结构与启动

后端采用按业务功能组织的模块化单体：

```text
app/
├── main.py
├── core/
├── conversations/
│   └── memory/
├── profile/
├── llm/
├── storage/
└── exceptions/
```

- `conversations`：会话聚合、剧情分支、历史持久化及 HTTP 接口。
- `conversations/memory`：只属于会话生命周期的 Context 与压缩能力。
- `profile`：独立于单个会话的全局角色设定。
- `llm`：模型目录、连接测试及供应商调用适配。
- `storage`：跨业务模块复用的底层 JSON 文件能力。

FastAPI 只保留一个正式入口：

```powershell
uvicorn app.main:app --reload
```

## 13. 验证

```powershell
python -m unittest discover -s test -p "test_*.py" -v
python -m compileall -q app test
```

逐模块设计与交付记录位于 `docs/context_refactor/`。
