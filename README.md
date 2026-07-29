# 版本化会话引擎

这是一个支持长程上下文、消息重写和会话分支的通用 FastAPI 后端。

当前仓库只保留通用基础设施，不包含具体产品领域、全局角色设定或业务工作流。

## 核心能力

- 一个 `Turn` 保存一次完整的用户输入与助手回复。
- Turn 通过 `parent_turn_id` 组成可分叉的历史树。
- 每个 Branch 使用 `head_turn_id` 标记当前历史终点。
- 修改旧消息时创建新 Branch，不覆盖原始历史。
- 摘要采用追加式版本链，不删除原文。
- Context 超过高水位后，按完整 Turn 边界执行同步压缩。
- 压缩期间会校验 HEAD、pending Turn 和活动摘要，丢弃过期结果。
- 无法安全压缩时只降级本次发送副本，持久化数据保持完整。

## 数据模型

```text
Conversation
├── turns: Turn 原始轮次索引
├── branches: Branch 会话分支索引
├── summaries: SummaryVersion 摘要版本索引
└── active_branch_id: 当前活动分支
```

### Turn

```text
turn_id
parent_turn_id
user_content
assistant_content
status: pending | completed | failed
```

每个 Turn 最多有一个父 Turn；多个 Turn 可以共享同一个父 Turn，从而形成分支。

### Branch

```text
branch_id
parent_branch_id
forked_from_turn_id
head_turn_id
pending_turn_id
active_summary_id
```

Branch 是一组可移动书签，不复制共同历史。

### SummaryVersion

```text
summary_id
parent_summary_id
covered_until_turn_id
content
```

新摘要通过 `parent_summary_id` 连接旧摘要，并通过
`covered_until_turn_id` 标记覆盖到的完整 Turn。

## Context 组装

一次主对话请求按以下顺序组装：

```text
活动摘要（如有）
→ 尚未被摘要覆盖的 completed Turn
→ 当前 pending 用户输入
```

`pending` Turn 只参与当前主对话，不参与本轮压缩。最终发送给 LLM 的
messages 不持久化，需要时根据会话状态重新构建。

## 压缩水位

默认配置：

```text
CONTEXT_HIGH_WATERMARK=40000
CONTEXT_LOW_WATERMARK=25000
RECENT_RAW_TOKEN_TARGET=10000
SUMMARY_TOKEN_BUDGET=1000
MAX_COMPRESSION_PASSES=3
CONTEXT_SAFETY_MARGIN=200
```

只有 Context 严格超过高水位才触发压缩。压缩规划器选择连续完整 Turn，
为摘要预留空间，并尽量保留接近 `RECENT_RAW_TOKEN_TARGET` 的近期原文。

## HTTP 接口

```text
POST /conversations
GET  /conversations/{conversation_id}/history
POST /conversations/{conversation_id}/turns
POST /conversations/{conversation_id}/turns/{turn_id}/rewrite
GET  /conversations/{conversation_id}/turns/{turn_id}/variants
POST /conversations/{conversation_id}/branches/{branch_id}/activate
```

LLM 配置和连接测试接口位于 `/llm`。

## 项目结构

```text
app/
├── conversations/       会话聚合、分支、历史与 HTTP 接口
│   └── memory/          Context 规划、压缩和降级
├── core/                配置、依赖注入、日志与错误映射
├── exceptions/          业务异常
├── llm/                 模型设置、客户端与连接测试
└── storage/             通用 JSON 文件存储

data/
└── conversations/       运行时会话数据

test/                    后端自动化测试
test_frontend.py         最小测试界面
```

## 运行

安装依赖：

```powershell
pip install -r requirements.txt
```

启动后端：

```powershell
uvicorn app.main:app --reload
```

运行测试：

```powershell
python -m unittest discover -s test -v
```

## 扩展边界

具体产品应建立独立业务模块，并通过明确的项目 ID 加载自己的状态。
不要把项目级设定重新放回全局单例，也不要把资产、工具调用或生成任务
塞进 `assistant_content`。
