# s08: 子代理 / 上下文隔离 (Subagent)

`s01 > s02 > s03 > s04 | s05 > s06 | s07 > [ s08 ]`

> *"派小太监去办差"* —— 把细节执行外包到独立上下文, 主线只听汇报。
>
> **架构层**: 嵌套循环 + 上下文压缩。

## 问题

工具用得越多, 主 history 越脏:

- 一次 `web_fetch` 抓回 8000 字网页;
- 一次 `ls -R` 输出几百行;
- 反复试错的命令日志、粘进来的报错栈。

这些细节对**最终回答**几乎无用, 但会:

1. 占 token, 让对话越来越贵、越来越慢;
2. 稀释模型注意力, 后续推理质量下滑;
3. 触发上下文窗口上限, 早早把对话掐断。

## 解决方案

把"细节执行"外包给一个**独立的 message loop** (子代理):

- 自己的 messages 列表 (不与主 history 共享);
- 自己的 system prompt (小太监人设);
- 工具集**不含** `dispatch_subagent` (防递归) 与 `update_todos` (防状态污染);
- 跑完只把**最终一段文本**作为单条 `tool_result` 回传主 agent。

```
主 agent history:
  ... user ... assistant tool_use(dispatch) ... tool_result("总结 200 字") ...
                                                          ▲
                                                          │  不管子代理
                                                          │  内部跑了 N 轮
   子代理独立上下文 (用完即弃):
       user(差事) → llm → tool → llm → tool → ... → final_text
       └────────── 只这一段回传主 agent ──────────┘
```

## 工作原理

1. **公共工具分发函数**, 主/子共用 (s06 那段 if/elif 抽出来):

```python
def execute_basic_tool(block, prefix=""):
    if block.name == "run_command":
        return subprocess.run(block.input["command"], ...).stdout
    elif block.name == "web_fetch":
        return web_fetch(block.input["url"], ...)
    elif block.name == "load_skill":
        return SKILL_LOADER.get_content(block.input["skill_name"])
```

`prefix="子·"` 让终端打印能区分主/子上下文。

2. **子代理函数**, 独立 messages, max_turns 上限防跑飞:

```python
def run_subagent(task, purpose="", max_turns=10):
    messages = [{"role": "user", "content": task}]
    for _ in range(max_turns):
        msg = client.messages.create(
            model=MODEL,
            system=SUBAGENT_SYSTEM_PROMPT,
            tools=SUBAGENT_TOOLS,           # ← 不含 dispatch / update_todos
            messages=messages,
        )
        messages.append({"role": "assistant", "content": msg.content})
        if msg.stop_reason != "tool_use":
            return next(b.text for b in msg.content if b.type == "text")
        results = [
            {"type": "tool_result", "tool_use_id": b.id,
             "content": execute_basic_tool(b, prefix="子·")}
            for b in msg.content if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})
    return "（小太监未能在限定回合内办妥差事）"
```

3. **主 agent 多一个工具** `dispatch_subagent(task, purpose)`, 调用 `run_subagent`, 把返回值作为单条 `tool_result.content` 写回主 history。

4. **可视化上下文压缩**:

```
[派遣小太监 #1]: 抓 HN 头条
  ┌── subagent context start ──
  [子·网页获取]: https://news.ycombinator.com
  [子·执行命令]: ...
  └── subagent context end (内部 4 轮, 回传 215 字) ──
[小太监回禀]: ...(摘要)...
[主上下文压缩]: 子代理仅向主 history 追加 215 字
```

5. **沿用 s07 的收尾闭环**: 主 agent 的外层 `while` 在 `stop_reason != "tool_use"` 时仍会校验 `TODOS`, 残单回推 + `continue`, 全完则 `TODOS = []` 重置。这条机制不因引入子代理而失效 —— 子代理只负责"执行细节", 计划状态依旧由主 agent 拥有:

```python
if message.stop_reason != "tool_use":
    if TODOS:
        unfinished = [t for t in TODOS if t["status"] != "completed"]
        if unfinished:
            history.append({"role": "user", "content":
                "差事尚未办妥, 以下任务仍未完成, 请按计划继续执行:\n"
                + render_todos(TODOS)})
            continue
        print("[最终计划状态 - 全部办妥]")
        TODOS = []
    break
```

注意子代理工具集**不含** `update_todos`, 所以它无法私改主 todolist; 它的"完成"只是子任务局部完成, 是否真办妥仍由主 agent 在收尾时校验。

完整代码: [code/step08_subagent.py](../code/step08_subagent.py)

## 变更内容

| 组件          | 之前 (s07)              | 之后 (s08)                                       |
|---------------|-------------------------|--------------------------------------------------|
| 工具数        | 4                       | 5 (新增 `dispatch_subagent`)                     |
| 上下文模型    | 单一 history            | 主 + 子隔离                                       |
| 工具分发      | 重复 if/elif            | 抽出 `execute_basic_tool` 共用                   |
| 防御机制      | 单 in_progress + 残单回推 | + `max_turns` 限流 + 子代理工具白名单防递归    |
| 终端打印      | 单层                    | 双层缩进, 显式 context start/end                 |
| 收尾闭环      | 已具备 (校验 + 重置)    | 沿用; 子代理无 `update_todos`, 不能私改主计划   |

## 试一试

```sh
python build-agent-example/code/step08_subagent.py
```

- `派一个小太监去 ls -1 build-agent-example/code/, 把文件名整理成一句话回报朕`
- `派小太监去抓 https://example.com 和 https://example.org, 给朕一句话总结两站差异`
- `朕要写报告 -- 派一队小太监分别去查 build-agent-example/code 下每个 step 文件的代码行数, 整理成表格`

观察 `[派遣小太监] ... [小太监回禀] ... [主上下文压缩]: X 字` —— 子代理跑了多少轮工具调用, 主 history 都只多 1 条结果。

教学闭环完成: s05 让 agent 能动手, s07 让它会规划, s08 让它能委派。
