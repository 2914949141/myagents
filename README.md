# Agent-Hemo（血智）

面向血站/血浆站场景的自研 AI Agent 框架，从零实现 ReAct 循环、工具调用、三层记忆、RAG 检索、多 Agent 协作、LangGraph 工作流、HTTP API 与 MCP 协议暴露。

---

## 目标与背景

血站日常运营涉及大量规范文档（献血法、国标、操作规程）和时效性业务（血浆临期、采血日报、钉钉预警）。传统信息化系统以表单和报表为主，**难以用自然语言快速问答、自动汇总和主动告警**。

Agent-Hemo 的目标是：在可控、可观测、可扩展的前提下，构建一套**能落地到血站场景**的 Agent 运行时——既能回答规范问题，也能调用工具完成日报生成、临期统计和 Webhook 推送。

---

## 项目定位


| 维度       | 说明                                                 |
| -------- | -------------------------------------------------- |
| **是什么**  | 自研 Agent 框架 + 血站垂直应用，不是 LangChain 套壳 Demo          |
| **面向谁**  | 血站信息科、血浆站运营、AI 应用工程师（面试作品集）                        |
| **核心差异** | 代码与数据分离、工具可注册、MCP 可对接 Cursor、告警可编排（LangGraph + 钉钉） |
| **不是什么** | 不是通用低代码平台，也不是仅 CLI 聊天机器人                           |


---

## 项目结构

```
Agent-Hemo/                      # 项目根目录（在此执行所有命令）
├── .env                         # 环境变量（密钥，不提交 Git）
├── .env.example
├── pyproject.toml               # 包定义 + 依赖
├── README.md
│
├── agent_hemo/                  # Python 包（Agent 运行时）
│   ├── main.py                  # CLI 入口
│   ├── agent_loop.py            # 对话管理
│   ├── agent_runner.py          # ReAct 核心循环
│   ├── settings.py              # 统一配置（读 .env）
│   ├── core/                    # LLM 客户端
│   ├── tools/                   # 工具集（自动注册）
│   ├── memory/                  # 三层记忆逻辑
│   ├── rag/                     # 检索逻辑（FAISS + BM25 混合）
│   ├── workflows/               # LangGraph 告警工作流
│   ├── api/                     # FastAPI 服务
│   ├── mcp_server/              # MCP 协议
│   ├── utils/                   # 日志、沙箱、Token 统计
│   └── static/                  # chat.html
│
├── knowledge/                   # RAG 知识库（.md 语料）
├── data/                        # 运行时数据
│   ├── memory/                  # Agent 记忆文件
│   ├── reports/                 # 生成的日报 / 告警报告
│   ├── rag_index/               # 向量索引（可重建）
│   ├── skills/                  # SKILL.md 技能定义
│   └── sources/                 # pptx/pdf 原始文档
├── logs/                        # JSONL 运行日志
├── scripts/                     # 工具脚本（转 md、统计等）
└── tests/                       # 单元测试 + eval
```

---



## 项目亮点

1. **完整 Agent 运行时**：ReAct 循环 + Function Calling + Reflexion 反思重试 + 并行子 Agent 派遣
2. **三层记忆**：原始对话层 / 日记忆情景层 / MEMORY.md 长期层，支持跨会话持久化
3. **混合 RAG**：FAISS 向量检索 + BM25 关键词 + Reranker，manifest 失效检测自动重建索引
4. **Skill 按需加载**：SKILL.md 描述注入 system prompt，详情通过 `load_skill` 工具按需读取
5. **安全沙箱**：文件读写限制在工作区内，shell 命令白名单 + 危险操作确认
6. **可观测性**：JSONL 结构化日志（AgentTracer）+ Token 累计统计
7. **工程化 API**：FastAPI 提供 `/chat`、`/report`、`/alerts/run`、SSE 流式；APScheduler 定时预警
8. **LangGraph 工作流**：临期血浆告警支持人工确认节点 + SQLite checkpoint 持久化
9. **MCP 集成**：工具通过 FastMCP 暴露给 Cursor 等 IDE
10. **标准项目布局**：`pip install -e .` 后可在项目根目录直接运行

---



## 快速开始



### 1. 安装

```powershell
cd Agent-Hemo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```



### 2. 配置

```powershell
copy .env.example .env
# 编辑 .env，填入 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID
```



### 3. 运行 CLI

```powershell
python -m agent_hemo.main
# 或
agent-hemo
```



### 4. 启动 HTTP API

```powershell
python -m agent_hemo.api.main
# 或
uvicorn agent_hemo.api.main:app --host 0.0.0.0 --port 8000
```


| 端点                      | 说明               |
| ----------------------- | ---------------- |
| `GET /health`           | 健康检查             |
| `POST /chat`            | 问答               |
| `POST /chat/stream`     | SSE 流式问答         |
| `POST /report`          | 生成采血日报           |
| `POST /alerts`          | 临期血浆 JSON 汇总     |
| `POST /alerts/run`      | 告警流水线（报告 + 可选钉钉） |
| `GET /static/chat.html` | 浏览器流式测试页         |
| `GET /docs`             | Swagger 文档       |




### 5. MCP Server

```powershell
python -m agent_hemo.mcp_server
```

Cursor 配置示例：

```json
{
  "mcpServers": {
    "agent-hemo": {
      "command": "D:\\path\\to\\Agent-Hemo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "agent_hemo.mcp_server"],
      "cwd": "D:\\path\\to\\Agent-Hemo"
    }
  }
}
```



### 6. 运行测试

```powershell
pytest tests/ -v -m "not integration"
```

---



## 配置说明

所有配置由 `agent_hemo/settings.py` 读取项目根目录下的 `.env`。


| 变量               | 默认值                 | 说明             |
| ---------------- | ------------------- | -------------- |
| `LLM_API_KEY`    | —                   | API 密钥（必填）     |
| `LLM_BASE_URL`   | —                   | API 地址（必填）     |
| `LLM_MODEL_ID`   | `gpt-3.5-turbo`     | 模型 ID          |
| `KNOWLEDGE_DIR`  | `./knowledge`       | RAG 知识库目录      |
| `MEMORY_DIR`     | `./data/memory`     | 记忆存储           |
| `SKILLS_DIR`     | `./data/skills`     | 技能目录           |
| `RAG_INDEX_DIR`  | `./data/rag_index`  | 向量索引           |
| `ALERT_CSV_PATH` | `data/bag_info.csv` | 告警 CSV         |
| `WEBHOOK_URL`    | —                   | 钉钉 Webhook（可选） |


---



## 内置工具


| 工具名                              | 说明                  |
| -------------------------------- | ------------------- |
| `plan`                           | 多步骤任务计划             |
| `dispatch_subagent`              | 派遣子 Agent（产品/开发/测试） |
| `rag_search`                     | 知识库语义检索             |
| `load_skill`                     | 加载技能详情              |
| `read_file` / `write_file`       | 工作区内文件读写            |
| `run_command`                    | 白名单 shell 命令        |
| `web_fetch`                      | 抓取网页                |
| `save_to_memory` / `read_memory` | 长期记忆读写              |
| `generate_blood_report`          | 采血日报                |
| `check_plasma_expiry`            | 临期血浆检查              |


---



## 踩坑记录



### 1. Python 包路径与项目根目录混淆

早期把包目录和 monorepo 父目录混在一起，必须 `cd ..` 才能 `python -m myagents.main`。

**解决**：采用标准布局——项目根目录放 `.env`，Python 包放在 `agent_hemo/` 子目录，`pip install -e .` 后在项目根即可运行。

### 2. setuptools 包发现映射错误

用 `package-dir = {"myagents": "."}` 时，自动发现会把 `tools/`、`api/` 注册为顶层包，导致 `import myagents` 失败。

**解决**：项目根与包目录分离后，使用 `include = ["agent_hemo*"]` 即可正确发现子包。

### 3. RAG 索引路径变更后检索为空

移动知识库目录（`docs/md` → `knowledge/`）后，旧 manifest 中的路径失效。

**解决**：manifest 按源文件 mtime/size 校验，路径不匹配会自动重建；也可手动删除 `data/rag_index/` 强制重建。

### 4. FastAPI StaticFiles 路径

静态文件在 `agent_hemo/static/`，不在项目根 `static/`。

**解决**：`settings.py` 中区分 `PROJECT_ROOT` 与 `PACKAGE_ROOT`，静态目录用 `PACKAGE_ROOT / "static"`。

### 5. Windows 下 embedding 模型内存占用

默认多语言模型 `paraphrase-multilingual-MiniLM-L12-v2` 在内存不足时可能 OOM。

**解决**：`.env` 改用 `RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2`，或设置 `HF_ENDPOINT` 镜像加速下载。

### 6. 钉钉 Webhook 加签

仅配置 URL 不够，启用加签时需同时设置 `WEBHOOK_SECRET`。

**解决**：集成测试用 `pytest -m integration`，本地开发可先 `send_notify=false` 只验证报告生成。

---



## 学后收获

- 理解 Agent 运行时本质：**LLM 决策循环 + 工具执行 + 状态管理**，而非简单 prompt 工程
- 掌握 Function Calling 工具注册表设计：子类自动注册、OpenAI schema 生成、并行执行
- 实践 RAG 全链路：分块 → embedding → FAISS → BM25 混合 → Reranker → manifest 缓存失效
- 理解记忆分层：何时写原始层、何时压缩为日记忆、何时沉淀到 MEMORY.md
- 熟悉 MCP 协议：BaseTool 桥接、Cursor 集成
- 掌握 LangGraph 有状态工作流：checkpoint、人工确认节点、条件分支
- 建立**代码与数据分离**的项目工程习惯，便于部署和面试讲解

---



## 扩展建议


| 方向          | 建议                                            |
| ----------- | --------------------------------------------- |
| **RAG 增强**  | 引入 GraphRAG、HyDE、多路召回融合；支持 PDF 表格解析           |
| **记忆升级**    | 向量记忆检索、自动遗忘策略、用户画像                            |
| **多 Agent** | 引入 Supervisor 模式、Agent 间消息总线、任务队列             |
| **可观测性**    | 接入 OpenTelemetry、LangSmith/Langfuse 追踪        |
| **部署**      | Docker Compose + 独立向量库；API 鉴权升级 JWT           |
| **评估**      | 扩充 `tests/agent_eval` 用例；引入 LLM-as-Judge 自动评分 |
| **业务**      | 对接 LIS/HIS 接口；扩展成分血、检测质控等场景                   |


---



## 技术栈

Python 3.10+ · OpenAI 兼容 API · FAISS · SentenceTransformers · FastAPI · LangGraph · MCP · APScheduler · pytest

---



## License

Personal learning project.