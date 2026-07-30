# 后端逐文件说明

这份文档按“某个板块出了问题时去哪里找”的方式组织。学习产品的新后端
不保存用户会话；仓库原有 `app/conversations/` 仍作为旧版通用会话引擎
保留，学习地图正式使用的是 `app/learning/`。

## 应用入口与组合根

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/main.py` | 创建 FastAPI、配置 CORS、注册路由和统一异常响应 | 服务起不来、路由不存在、跨域失败 |
| `app/core/config.py` | 集中读取路径、压缩水位和允许的前端域名 | 环境变量没有生效、索引路径错误 |
| `app/core/dependencies.py` | 只在这里组装仓库、检索器、上下文服务和编排器 | 依赖替换、测试注入、启动时加载错误 |
| `app/core/error_mapping.py` | 把领域异常转换为稳定 HTTP 状态和错误码 | 前端收到错误状态不正确 |
| `app/core/logger.py` | 日志格式和级别 | 看不到阶段日志 |

## 学习图领域层

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/learning/domain/models.py` | Turn、Branch、Summary、Citation 和整张图的不变量 | 图引用错误、循环、端口重复、方向错误 |
| `app/learning/domain/graph_policy.py` | 根节点、普通续写、转弯分支的放置策略 | 节点为什么不能创建、分支为何选错方向 |
| `app/exceptions/learning_errors.py` | 学习图和上下文专用异常 | 错误类型需要细分 |

## 前后端命令契约

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/learning/contracts/commands.py` | 浏览器提交的稳定命令、紧凑图、当前路径和固定背景 | 422 参数错误、前后端字段不一致 |
| `app/learning/contracts/delta.py` | 后端返回的原子增量和分支末端更新 | 本地无法落库、修订号不连续 |
| `app/learning/routes.py` | `POST /learning/conversations/turns`，从 Header 读取请求级 Key | 学习问答接口进不去或 Header 缺失 |

## 学习应用层

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/learning/application/snapshot_adapter.py` | 把紧凑图还原为可执行领域图 | 服务端图校验与前端显示不一致 |
| `app/learning/application/path_validator.py` | 校验当前原文路径连续且不混入兄弟分支 | 回答继承了错误分支、路径被拒绝 |
| `app/learning/application/context_service.py` | 组装 Prompt、背景、摘要、原文、RAG；必要时生成摘要 | 模型忘记进度、上下文超限、摘要异常 |
| `app/learning/application/turn_orchestrator.py` | 串联图验证、检索、压缩、模型、引用和 Delta | 一次正式问答的整体流程错误 |
| `app/learning/observability.py` | 记录 validation/retrieval/context/model/complete 阶段 | 定位慢在哪一步、操作 ID 查不到 |

## 模型层

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/llm/contracts.py` | 消息、结果、来源、用量、能力和工厂 Protocol | 新厂商需要接入或上游依赖变乱 |
| `app/llm/settings.py` | 厂商目录、模型白名单、SDK、上下文和能力标记 | 模型下拉项错误、模型被拒绝 |
| `app/llm/runtime_factory.py` | 每个请求创建独立客户端并选择适配器 | Key 串用、厂商适配器选错 |
| `app/llm/client.py` | 普通非联网 SDK 调用和异常归一化 | 普通问答失败、SDK 参数错误 |
| `app/llm/connection_service.py` | 使用严格“连接成功”探针验证模型 | 连接测试误判 |
| `app/llm/schemas.py` | 模型目录与连接测试 HTTP 模型 | 连接页面 422 |
| `app/llm/routes.py` | `GET /llm/presets`、`POST /llm/connection-test` | 模型列表或连接接口异常 |

## 厂商联网适配器

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/llm/providers/common.py` | 普通调用、字段兼容读取、来源去重 | 不同 SDK 对象格式无法解析 |
| `app/llm/providers/errors.py` | OpenAI/Anthropic SDK 异常转应用异常 | 前端看到厂商原始异常 |
| `app/llm/providers/plain.py` | 不支持联网的厂商及降级策略 | DeepSeek/MiniMax 搜索模式行为 |
| `app/llm/providers/openai_search.py` | OpenAI 与 xAI Responses Web Search | OpenAI/xAI 搜索或引用丢失 |
| `app/llm/providers/anthropic_search.py` | Claude 服务端 Web Search 和引用解析 | Claude 搜索块解析失败 |
| `app/llm/providers/glm_search.py` | GLM 对话内搜索和搜索结果解析 | GLM 搜索未执行、`ref_` 来源警告 |
| `app/llm/providers/__init__.py` | 对外导出适配器 | 工厂无法导入新适配器 |

## 公共知识库

| 文件 | 职责 | 出问题时首先检查 |
| --- | --- | --- |
| `app/retrieval/contracts.py` | 检索命中、结果和 Retriever Protocol | 替换检索实现时的边界 |
| `app/retrieval/manifest.py` | 源资料和构建产物清单校验 | manifest 格式、越界路径、重复 ID |
| `app/retrieval/chunking.py` | 按稳定长度切分权威文本 | 片段过大、断句不合理 |
| `app/retrieval/embedding.py` | 固定 FastEmbed 中文模型，延迟加载 | 首次向量化、模型下载或维度错误 |
| `app/retrieval/keyword_index.py` | SQLite FTS5 三字符索引和 BM25 查询 | 中文关键词搜不到 |
| `app/retrieval/vector_index.py` | FAISS 向量索引的构建、保存和查询 | 语义检索、维度或索引文件错误 |
| `app/retrieval/hybrid_retriever.py` | 两路查询、RRF 融合和单路降级 | 排序异常、某个索引故障拖垮全部查询 |
| `app/retrieval/builder.py` | 读取清单、切片并生成全部部署产物 | 知识库构建失败 |
| `app/retrieval/schemas.py` | 知识库信息 HTTP 响应 | 信息接口字段错误 |
| `app/retrieval/routes.py` | `GET /knowledge-base/info` | 前端无法读取知识库版本 |
| `scripts/build_knowledge_base.py` | 可直接运行的离线构建命令 | 构建入口、输入输出目录 |
| `knowledge_base/sources/manifest.json` | 人工维护的权威资料目录 | 加资料、升级知识库版本 |
| `knowledge_base/indexes/manifest.json` | 当前部署索引的版本与规模 | 后端加载了哪一版索引 |

## 测试定位

| 文件 | 覆盖内容 |
| --- | --- |
| `test/test_learning_contracts.py` | Command/Delta 字段和修订号 |
| `test/test_learning_graph.py` | 根节点、方向、端口和分支规则 |
| `test/test_learning_orchestrator.py` | 无状态问答、路径、摘要、引用和路由 |
| `test/test_llm_runtime_factory.py` | 请求级 Key、厂商搜索、来源和用量 |
| `test/test_retrieval.py` | 构建、混合检索、空库和故障降级 |
| `test/test_main.py` | 产品入口、路由和本地跨域 |

## 最常见修改路径

- 新增模型：先改 `settings.py`，再决定复用哪个 `providers/` 适配器，最后补
  `test_llm_runtime_factory.py`。
- 修改分支规则：只改 `graph_policy.py` 和领域校验，再补
  `test_learning_graph.py`。
- 修改上下文顺序：只改 `context_service.py`，不要在路由或厂商适配器拼
  Prompt。
- 替换本地知识库：实现 `KnowledgeRetriever` 契约并在
  `core/dependencies.py` 更换组合。
- 修改 HTTP 字段：先更新 `contracts/`，同时更新前端
  `shared/contracts/`，两边测试必须一起通过。
