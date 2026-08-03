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
DELETE /conversations/{conversation_id}
GET  /conversations/{conversation_id}/history
POST /conversations/{conversation_id}/turns
POST /conversations/{conversation_id}/turns/{turn_id}/rewrite
GET  /conversations/{conversation_id}/turns/{turn_id}/variants
POST /conversations/{conversation_id}/branches/{branch_id}/activate
GET  /conversations
```

LLM 配置、连接测试和运行时模型切换接口位于 `/llm`。前端默认连接 `http://127.0.0.1:8000`，可通过 `frontend/.env` 中的 `VITE_API_BASE_URL` 覆盖。

完成的历史 Turn 会通过 `response_duration_ms` 保存本次响应耗时。开发环境可用 `?preview=waiting`、`?preview=llm` 和 `?preview=network` 预览等待、模型异常和网络异常界面；这些参数不会触发真实模型请求。

## 性能面板

每次成功对话会旁路记录以下指标：

```text
总耗时、Context 耗时、LLM 耗时、输入 Token 估算、
压缩轮数、是否发生质量降级
```

指标默认追加到 `data/performance.csv`，记录失败不会影响聊天结果。

启动后端后访问：

```text
http://127.0.0.1:8000/performance
```

页面提供耗时概览、P95、压缩与降级比例、趋势图和最近请求表格。
只读数据接口为 `GET /performance/data`。

## 项目结构

```text
app/
├── conversations/       会话聚合、分支、历史与 HTTP 接口
│   └── memory/          Context 规划、压缩和降级
├── core/                配置、依赖注入、日志与错误映射
├── exceptions/          业务异常
├── llm/                 模型设置、客户端与连接测试
├── performance/         旁路性能记录与只读仪表盘
└── storage/             通用 JSON 文件存储

data/
└── conversations/       运行时会话数据

test/                    后端自动化测试
test_frontend.py         最小测试界面
```

## 运行

需要分别启动后端和前端，建议打开两个 PowerShell 窗口。

### 启动后端

在项目根目录执行：

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：`http://127.0.0.1:8000`

模型厂商、默认模型和 API Key 配置位于项目根目录的 `.env`。

### 启动前端

新开一个 PowerShell 窗口，在项目根目录执行：

```powershell
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

### 运行测试（可选）

```powershell
python -m unittest discover -s test -v
cd frontend
npm run build
```

## 扩展边界

具体产品应建立独立业务模块，并通过明确的项目 ID 加载自己的状态。
不要把项目级设定重新放回全局单例，也不要把资产、工具调用或生成任务
塞进 `assistant_content`。
