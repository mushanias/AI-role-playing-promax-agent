# 角色扮演 Agent 后端

这是一个使用 FastAPI、JSON 持久化和 OpenAI 兼容 LLM 接口构建的角色扮演对话后端。

当前后端 MVP 支持：

- 以完整 Turn 保存用户输入和助手回复；
- 原始历史、旧摘要和旧剧情分支永不覆盖；
- 修改任意旧用户消息并从该轮重新生成剧情；
- 查询同一位置的消息版本并切换活动分支；
- 使用追加式摘要版本控制长上下文；
- 40k Context 质量高水位、25k 压缩软目标和约 10k 近期原文目标；
- 极端超长时降级本次发送载荷，同时保留完整 JSON 原文并返回 warning。

## 数据文件

```text
data/
├── profile.json
└── conversations/
    └── {conversation_id}.json
```

`profile.json` 是一份全局开局设定。后续剧情设定作为对话原文保存。

每个会话单独使用一个 JSON 文件，包含：

- `turns`：所有原始轮次，包括旧分支和失败输入；
- `branches`：剧情分支、HEAD、pending 和活动摘要指针；
- `summaries`：追加保存的摘要版本链；
- `active_branch_id`：界面当前使用的剧情分支。

## 配置

在项目根目录创建 `.env`：

```dotenv
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

PROFILE_PATH=data/profile.json
CONVERSATIONS_PATH=data/conversations

CONTEXT_HIGH_WATERMARK=40000
CONTEXT_LOW_WATERMARK=25000
RECENT_RAW_TOKEN_TARGET=10000
CONTEXT_SAFETY_MARGIN=200
SUMMARY_TOKEN_BUDGET=1000
MAX_COMPRESSION_PASSES=3
```

`SUMMARY_TOKEN_BUDGET` 是一次压缩允许保留的最小摘要空间；实际摘要上限会根据设定、近期原文和当前输入动态计算。

## 启动

安装依赖后运行：

```powershell
uvicorn app.api:app --reload
```

也可以运行命令行对话：

```powershell
python -m app.main
```

## HTTP API

### 创建会话

```http
POST /conversations
```

### 读取当前原文历史

```http
GET /conversations/{conversation_id}/history
GET /conversations/{conversation_id}/history?branch_id={branch_id}
```

### 发送消息

```http
POST /conversations/{conversation_id}/turns
Content-Type: application/json

{
  "message": "用户输入",
  "branch_id": null
}
```

成功响应包含 `warnings` 和 `quality_degraded`。界面应将 warning 显示为提示，不应把它当作发送失败。

### 修改旧消息

```http
POST /conversations/{conversation_id}/turns/{turn_id}/rewrite
Content-Type: application/json

{
  "message": "修改后的用户输入",
  "source_branch_id": null
}
```

修改第 N 轮会保留前 N-1 轮并创建新分支，旧分支不会删除。

### 查询消息版本

```http
GET /conversations/{conversation_id}/turns/{turn_id}/variants
```

历史中的 `has_variants=true` 时，前端可以显示左右箭头。

### 切换分支

```http
POST /conversations/{conversation_id}/branches/{branch_id}/activate
```

## 错误响应

实际业务错误使用统一格式：

```json
{
  "error": {
    "code": "branch_not_found",
    "message": "剧情分支不存在：..."
  }
}
```

不存在的资源返回 `404`，状态冲突返回 `409`，LLM 上游错误返回 `502/503`。Context 超过质量水位时使用成功响应中的 `warnings`，不返回预算错误。

## 验证

```powershell
python -m unittest discover -s test -p "test_*.py" -v
python -m compileall -q app test
```

上下文重构的逐模块交付说明位于 `docs/context_refactor/`。
