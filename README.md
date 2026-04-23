# Claude Agent 示例

用 Python 从零构建 AI Agent。包含两部分：

1. **`agent/`** — 一个完整可用的多轮对话 Agent，带三层记忆系统、自动压缩、可插拔技能。
2. **[build-agent-example/](build-agent-example/)** — 6 个渐进式教学示例（agent1 → agent6），从单次对话到 Tool Use + Skills。

配套讲解 PPT 见 [ppt/](ppt/)。

---

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install anthropic python-dotenv pyyaml jinja2

cp .env.example .env                      # 填入 ANTHROPIC_API_KEY

python agent.py                           # 启动主 Agent
# —— 或 ——
python build-agent-example/agent1.py      # 从最简单的教学示例开始
```

---

## 主 Agent（`agent.py` + `agent/` 包）

启动后是一个"大内总管 / 皇上"角色的命令行对话循环。

### 目录结构

```
agent.py                    入口（4 行）
agent/
├── loop.py                 主循环
├── runner.py               单轮 messages.create + tool_use 循环
├── memory.py               三层记忆存储
├── compactor.py            历史压缩 → 情景记忆 + MEMORY.md
├── context.py              system prompt 组装（Jinja2）
├── skills.py               技能加载器
├── telemetry.py            token 用量记录与压缩触发判断
└── tools/                  内置工具（shell / web / 文件 / glob / grep / load_skill）

templates/
├── SOUL.md                 Agent 灵魂档案（人格 / 使命 / 边界，只读）
├── USER.md                 用户偏好档案（压缩时按信号更新）
└── agent/
    ├── identity.md         工作区路径声明（Jinja2 模板）
    ├── skills_section.md   技能清单注入
    └── compact_prompt.md   压缩 LLM 的提示词

memory/                     运行期产物（已 gitignore）
├── MEMORY.md               长期记忆，每轮注入 system prompt
├── history.jsonl           原始对话日志
├── tokens.jsonl            按调用记录 token 用量
└── YYYY-MM-DD.md           每日情景记忆，压缩时生成

skills/                     可插拔技能包
└── {name}/SKILL.md         技能描述（YAML frontmatter + Markdown）
```

### 三层记忆系统

| 层 | 载体 | 何时写 | 何时读 |
|----|------|--------|--------|
| 工作记忆 | `history` 列表（内存） | 每轮追加 | 全量传给 LLM |
| 情景记忆 | `memory/YYYY-MM-DD.md` | 压缩触发时 | 按需 grep |
| 长期记忆 | `memory/MEMORY.md` | 压缩 / 启动归档时 | 每轮注入 system prompt |

**自动压缩**：上一次调用的 input_tokens 超过 `200_000 × 0.7 = 140K` 时，把 `history[:-10]` 喂给 LLM 提炼成情景段落 + 更新 MEMORY.md，只保留最近 10 轮。

**启动归档**：上次会话未达压缩阈值就退出 → 通过 `history.jsonl` 中的 `compact_event` 标记，启动时把未归档对话补归档，跨会话不丢上下文。

### 内置工具

| 工具 | 说明 |
|------|------|
| `run_command` | 执行 shell 命令 |
| `web_fetch` | 抓取 URL |
| `read_file` / `write_file` / `edit_file` | 工作区文件读写 |
| `glob` / `grep` | 工作区搜索 |
| `load_skill` | 按需加载 `skills/{name}/SKILL.md` 进上下文 |

---

## 教学示例 [build-agent-example/](build-agent-example/)

| 文件 | 能力 | 新增概念 |
|------|------|----------|
| [agent1.py](build-agent-example/agent1.py) | 单次对话 | API 调用基础 |
| [agent2.py](build-agent-example/agent2.py) | 连续对话 | 循环交互 |
| [agent3.py](build-agent-example/agent3.py) | 多轮记忆 | `messages[]` 历史 |
| [agent4.py](build-agent-example/agent4.py) | 角色设定 | system prompt |
| [agent5.py](build-agent-example/agent5.py) | Tool Use | 工具调用循环 |
| [agent6.py](build-agent-example/agent6.py) | 多工具 + Skills | 动态加载技能包 |

---

## Skills 系统

`skills/{name}/SKILL.md` 用 YAML frontmatter 描述触发条件，Markdown 写知识内容。Agent 在需要时通过 `load_skill` 工具按需加载，避免占用上下文窗口。

当前内置技能：

- `clawhub` — 技能库搜寻与安装
- `ddg-web-search` — DuckDuckGo 搜索
- `github` — GitHub CLI 交互
- `skill-creator` — 创建 / 更新技能
- `summarize` — URL / 播客 / 文件总结
- `weather` — 天气查询
- `web-ppt` — 生成网页式技术演讲稿

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | API 代理地址（可选） |

---

## 配套 PPT

[ppt/第一期:什么是agent.html](ppt/第一期:什么是agent.html) · [ppt/第二期:手搓agent.html](ppt/第二期:手搓agent.html) · [ppt/第三期:记忆系统.html](ppt/第三期:记忆系统.html)
