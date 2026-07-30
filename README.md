# 学习路径 Agent

一个把 AI 学习过程保存成“可分叉路径”的本地优先学习工具。

每一问一答都是一个真实节点。主线默认向下延伸；从旧知识点追问时，
新路径转弯但不改变原分支。用户可以在地图中拖动查看、单击预览、
双击切换当前位置，并随时展开从根节点到当前位置的完整问答历史。

## 当前 MVP 已实现

- React 前端与 FastAPI 后端完全分离。
- 多个学习目标，各自保存固定背景、目标、程度和 Prompt 快照。
- OpenAI、Anthropic、xAI、GLM、DeepSeek、MiniMax 模型预设与请求级热插拔。
- API Key 只保留在当前页面内存；关闭或刷新后需要重新输入。
- 每个完整的一问一答保存为一个节点。
- 主线向下、分支转弯、根节点禁止分支、每个端口只能使用一次。
- 单击节点查看当前路径，双击节点切换提问位置。
- 当前节点红框和小地图红色标记。
- 节点内容超过卡片范围时，通过“查看完整对话”打开完整内容。
- 公共固定知识库：SQLite FTS5 + FAISS + RRF 混合检索。
- 厂商原生联网搜索和统一来源引用。
- 浏览器 IndexedDB 本地存储、JSON 导入与导出。
- 长路径摘要压缩；摘要追加保存，不覆盖原问答。
- 结构化阶段日志与统一错误返回。

## 本地启动

### 1. 启动后端

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端接口文档：

```text
http://127.0.0.1:8000/docs
```

### 2. 启动前端

新开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

本地开发时，前端会把 `/api` 请求转发到
`http://127.0.0.1:8000`。

## 第一次使用

1. 选择模型厂商和模型，输入自己的 API Key。
2. 点击“测试并连接”，看到“连接成功”。
3. 填写这次学习目标的名称、背景、目标和程度。
4. 选择内置学习 Prompt，或填写自己的 Prompt。
5. 创建目标后，系统自动生成第一份学习规划。
6. 在输入框继续当前路径；需要追问时开启“分支模式”。
7. 单击节点预览路径，双击节点才会改变下一次提问位置。
8. 换设备前点击“导出”；新设备使用“导入”恢复。

完整操作说明见 [前端使用说明](docs/frontend_user_guide.md)。

## 公共知识库

当前仓库包含可部署的空索引，业务流程能够正常运行，但不会检索到资料。
加入正式权威资料时：

1. 把 `.md` 或 `.txt` 文件放入 `knowledge_base/sources/`。
2. 在 `knowledge_base/sources/manifest.json` 登记文件、标题、官方 URL、
   发布机构和版本号。
3. 执行：

```powershell
python scripts/build_knowledge_base.py
```

4. 重启后端，使只读检索器加载新索引。

构建使用固定小型中文向量模型 `BAAI/bge-small-zh-v1.5`。
关键词索引与向量索引分别检索，再通过 RRF 融合，不需要数据库服务。

## 验证

后端：

```powershell
python -m unittest discover -s test -v
```

前端：

```powershell
cd frontend
npm test
npm run build
```

前端还提供只用于交互测试的本地模拟接口：

```powershell
npm run mock-api
```

## 数据和隐私边界

- 学习目标、节点、分支、摘要和引用保存在浏览器 IndexedDB。
- 后端学习接口是无状态的，只接收当前图快照和当前路径。
- API Key 不写入 IndexedDB、导出文件、后端会话文件或日志。
- 浏览器清理站点数据会删除本地学习记录，请定期导出。
- 当前版本不提供账号同步；换设备不会自动出现旧数据。

## 分离部署

前端构建：

```powershell
cd frontend
$env:VITE_API_BASE_URL="https://你的后端域名"
npm run build
```

把 `frontend/dist/` 部署为静态站点。后端环境变量设置：

```text
CORS_ALLOWED_ORIGINS=https://你的前端域名
```

后端不需要云数据库，也不保存用户会话，因此可以部署到普通的 Python
容器或轻量云主机。用户数据仍只在各自浏览器中；这正是当前 MVP 的
成本与隐私取舍。

## 设计文档

- [产品架构与稳定契约](docs/product_architecture.md)
- [后端逐文件说明](docs/backend_file_guide.md)
- [前端使用说明](docs/frontend_user_guide.md)
- [开发约定](docs/development_conventions.md)
