# MyAgents - 模块化 AI Agent 框架

一个从零构建的个人 Agent 学习项目，实现了 ReAct 循环、工具调用、技能系统、三层记忆、RAG 检索、多 Agent 协作、可观测性与安全沙箱。

## 项目结构

```
myagents/
├── main.py                 # 程序入口
├── agent_loop.py           # 对话管理（prompt、history、用户输入）
├── agent_runner.py         # Agent 核心循环（LLM ↔ 工具 ↔ Reflexion）
├── config.py               # 统一配置（从 .env 读取）
├── core/
│   └── llm_client.py       # LLM 客户端（OpenAI 兼容 API + 流式）
├── tools/                  # 工具集（自动注册 + Function Calling）
├── memory/
│   ├── memory_store.py     # 三层记忆实现
│   └── memory/             # 记忆数据（history / 日记忆 / MEMORY.md）
├── rag/
│   ├── loader/             # Markdown 文档加载与分块
│   └── vector_store/       # FAISS 向量检索
├── skills/                 # SKILL.md 技能定义
├── utils/
│   ├── logger.py           # 结构化日志（AgentTracer）
│   ├── token_utils.py      # Token 统计
│   ├── sandbox.py          # 安全沙箱（命令白名单 + 路径限制）
│   └── skill_loader.py     # 技能加载器
├── docs/md/                # RAG 知识库文档
├── tests/                  # 单元测试
└── logs/                   # JSONL 运行日志
```

## 核心能力

| 能力 | 实现 | 关键文件 |
|------|------|----------|
| ReAct 循环 | 思考 → 调工具 → 观察 → 再思考 | `agent_runner.py` |
| 工具注册表 | 子类自动注册，OpenAI Function Calling | `tools/base_tool.py` |
| Skills | 按需加载 SKILL.md 知识 | `skills/`, `load_skill_tool.py` |
| 三层记忆 | 原始层 / 情景层 / 长期层 | `memory/memory_store.py` |
| RAG | FAISS + SentenceTransformer | `rag/vector_store/faiss_store.py` |
| 任务规划 | Plan 工具管理多步骤任务 | `tools/plan_tool.py` |
| 多 Agent | 产品经理 / 开发 / 测试子 Agent | `tools/dispatch_subagent_tool.py` |
| 并行子 Agent | 多个 dispatch_subagent 线程池并行 | `dispatch_subagent_tool.py` |
| Reflexion | 失败后自动反思重试 | `agent_runner.run_with_relexion` |
| 可观测性 | 结构化日志 + Token 统计 | `utils/logger.py`, `token_utils.py` |
| 安全沙箱 | 命令白名单 + 工作区路径限制 | `utils/sandbox.py` |

## 内置工具

| 工具名 | 说明 |
|--------|------|
| `plan` | 创建/更新多步骤任务计划 |
| `dispatch_subagent` | 派遣子 Agent（产品/开发/测试） |
| `rag_search` | 从知识库语义检索 |
| `load_skill` | 加载技能详细内容 |
| `read_file` / `write_file` | 读写文件（限工作区内） |
| `run_command` | 执行 shell 命令（白名单限制） |
| `web_fetch` | 抓取网页内容 |
| `save_to_memory` / `read_memory` | 长期记忆读写 |

## 快速开始

### 1. 安装依赖

```bash
cd myagents
pip install -r requirements.txt
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID
```

必填项：

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_ID=gpt-3.5-turbo
```

### 3. 运行

在仓库根目录 `claude-agent-examples` 下：

```bash
python -m myagents.main
```

或在 `myagents` 目录下：

```bash
python main.py
```

启动后输入问题，Agent 会自动选择工具回答。输入空行跳过，Ctrl+C 退出。

## 配置说明

所有配置由 `config.py` 统一读取 **`.env`**（不是 `.env.example`）。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | — | API 密钥（必填） |
| `LLM_BASE_URL` | — | API 地址（必填） |
| `LLM_MODEL_ID` | `gpt-3.5-turbo` | 模型 ID |
| `LLM_TIMEOUT` | `60` | 请求超时（秒） |
| `MEMORY_DIR` | `./memory/memory` | 记忆存储目录 |
| `SKILLS_DIR` | `./skills` | 技能目录 |
| `DOCS_DIR` | `./docs/md` | RAG 文档目录 |
| `MAX_TURNS` | `30` | 单次 run 最大步数 |
| `MAX_RETRIES` | `2` | Reflexion 最大重试次数 |
| `COMPACT_EVERY` | `5` | 每 N 轮助手回复后压缩历史 |
| `RAG_TOP_K` | `3` | RAG 默认返回文档数 |
| `COMMAND_TIMEOUT` | `30` | 命令执行超时（秒） |

## 架构概览

```
用户输入
  ↓
AgentLoop（对话管理、构建 prompt、恢复历史）
  ↓
AgentRunner.run_with_relexion（Reflexion 外层重试）
  ↓
AgentRunner.run（ReAct 循环）
  ├─ LLM 调用（流式 + Token 统计）
  ├─ 有 tool_calls → _execute_tools_parallel
  │    ├─ 普通工具：串行执行
  │    └─ 多个 dispatch_subagent：线程池并行
  └─ 无 tool_calls → 返回最终回复
       ↓
execute_basic_tool（统一入口 + 工具日志）
  ↓
各 Tool.execute()
```

### 日志

- 运行日志写入 `logs/YYYY-MM-DD.jsonl`（每行一条 JSON）
- `AgentRunner` 记录：`run_start` / `llm_start` / `llm_end` / `run_end` / `compact`
- `execute_basic_tool` 记录：`tool_start` / `tool_end`（含耗时与错误标记）

查看某次请求的完整轨迹：在日志中按 `trace_id` 过滤（主 Agent 的 trace 与子 Agent 可能不同 trace_id）。

## 测试

在仓库根目录 `claude-agent-examples` 下运行：

```bash
pytest myagents/tests/ -v
```

测试覆盖：

- `test_sandbox.py` — 路径检查、命令白名单
- `test_plan_tool.py` — Plan 状态逻辑
- `test_token_utils.py` — Token 累计
- `test_agent_runner.py` — Agent 循环（Mock LLM）
- `test_parallel_tools.py` — 子 Agent 并行耗时

若 `import myagents` 失败，确保 `myagents/tests/conftest.py` 已将项目根目录加入 `sys.path`，或设置 `PYTHONPATH=.`

## 开发指南

### 添加新工具

```python
# tools/my_tool.py
from myagents.tools.base_tool import BaseTool
import json

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述"

    @classmethod
    def get_parameters(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "参数说明"}
            },
            "required": ["query"]
        }

    def execute(self, tool_call) -> str:
        args = json.loads(tool_call.function.arguments)
        return f"处理结果: {args['query']}"
```

在 `tools/__init__.py` 中 import 该类即可自动注册。

### 添加新技能

```markdown
# skills/my_skill/SKILL.md
---
name: my_skill
description: 技能描述
---

# 技能内容
...
```

### 添加 RAG 文档

将 Markdown 文件放入 `docs/md/`，重启后首次调用 `rag_search` 时会自动加载建索引。

## 安全说明

- `read_file` / `write_file` 仅允许访问项目工作区内的路径
- `run_command` 使用命令白名单，危险命令模式会被拦截
- `.env` 含 API Key，已通过 `.gitignore` 排除，请勿提交

## 学习路线（本项目已涵盖）

1. LLM 调用与流式响应 → `core/llm_client.py`
2. ReAct 工具循环 → `agent_runner.py`
3. Skills 按需加载 → `skills/`, `load_skill_tool.py`
4. 三层记忆 → `memory/memory_store.py`
5. RAG 向量检索 → `rag/`
6. Plan + Multi-Agent → `plan_tool.py`, `dispatch_subagent_tool.py`
7. 可观测性（日志 + Token）→ `utils/logger.py`, `token_utils.py`
8. Reflexion 失败重试 → `run_with_relexion`
9. 安全沙箱 → `utils/sandbox.py`
10. 单元测试 → `tests/`
11. 配置中心化 → `config.py`
12. 子 Agent 并行 → `_execute_tools_parallel`

## 后续学习方向

| 方向 | 内容 |
|------|------|
| MCP 协议 | 与 Cursor 等 IDE 的工具生态对接 |
| LangGraph | 用图结构管理复杂 Agent 状态机 |
| 部署 API | FastAPI 包装 Agent，提供 HTTP 接口 |
| Agent 评估 | GAIA、SWE-bench 等 Benchmark |
| 真实项目 | 用本框架做文件整理、日报生成、代码审查等实用工具 |

建议先拿当前框架完成 1～2 个真实小项目，再考虑迁移到成熟框架。

## 相关文档

- [RAG 教程](docs/md/STEP8_RAG_README.md)

---

**祝使用愉快！**
