# Claude Agent 示例

用 Python 从零构建 AI Agent 的渐进式示例，基于 Anthropic Claude API。

## 示例概览

| 文件 | 能力 | 说明 |
|------|------|------|
| [agent1.py](agent1.py) | 单次对话 | 最简单的单轮问答 |
| [agent2.py](agent2.py) | 连续对话 | 循环接收输入，但无记忆 |
| [agent3.py](agent3.py) | 多轮记忆 | 维护对话历史，实现上下文连贯 |
| [agent4.py](agent4.py) | System Prompt | 设定角色人格（大内太监总管） |
| [agent5.py](agent5.py) | Tool Use | 赋予 Agent 执行 shell 命令的能力 |
| [agent6.py](agent6.py) | 多工具 + Skills | shell 命令 + 网页抓取 + 动态加载 Skill 知识 |

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install anthropic python-dotenv pyyaml
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 运行示例

```bash
python agent1.py   # 从最简单的开始
python agent6.py   # 完整功能版本
```

## 核心概念

每个示例新增一个关键概念：

```
agent1  →  API 调用基础
agent2  →  + 循环交互
agent3  →  + 对话历史（messages[]）
agent4  →  + system prompt / 角色设定
agent5  →  + tool_use（工具调用循环）
agent6  →  + 多工具 + Skill 动态加载
```

## Skills 系统（agent6）

`skills/` 目录下的每个子目录是一个可插拔的知识技能包，包含：
- `SKILL.md` — 技能描述与知识内容（YAML frontmatter + Markdown body）
- `_meta.json` — 元数据

Agent 在需要时调用 `load_skill` 工具按需加载，避免占用过多 context。

## 环境变量

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | API 代理地址（可选，默认官方地址） |
