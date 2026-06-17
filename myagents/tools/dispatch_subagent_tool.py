from myagents.tools.base_tool import BaseTool, execute_basic_tool
from concurrent.futures import ThreadPoolExecutor, as_completed



def build_subagent_prompt(title: str, duty: str, boundary: str) -> str:
    return (
        f"你是{title}，奉上级的专办的任务。\n"
        f"- 职务：{duty}\n"
        f"- 边界：{boundary}\n"
        "- 用工具尽快把差事办妥。\n"
        "- 只回禀结论与关键信息，不要复述每一步细节。\n"
        "- 你不能再派遣其他ai员工，所有差事自己跑工具完成。")


SUBAGENT_SPECS = {
    "product_manager": {
        "title": "产品经理",
        "system_prompt": build_subagent_prompt(
            "产品经理",
            "负责分析用户需求，编写产品开发大纲和用户需求说明书",
            "专注于需求分析和产品规划，不直接写代码",
        ),
        "tools": ["web_fetch", "load_skill", "read_file", "write_file"],
        "max_turns": 10,
    },
    "program_engineer": {
        "title": "软件开发工程师",
        "system_prompt": build_subagent_prompt(
            "软件开发工程师",
            "负责根据产品文档进行代码开发，创建和修改文件",
            "专注于代码实现，使用命令和文件操作完成开发任务",
        ),
        "tools": ["run_command", "read_file", "write_file"],
        "max_turns": 15,
    },
    "test_engineer": {
        "title": "测试工程师",
        "system_prompt": build_subagent_prompt(
            "测试工程师",
            "负责测试开发结果，发现问题并反馈给开发工程师",
            "专注于测试和问题发现，运行程序验证功能",
        ),
        "tools": ["run_command", "web_fetch", "read_file"],
        "max_turns": 10,
    }
}

SUBAGENT_TYPE_OPTIONS = list(SUBAGENT_SPECS.keys())


def _run_single_subagent(agent_type: str, task: str) -> str:
    from myagents.agent_runner import AgentRunner
    from myagents.core.llm_client import HelloAgentsLLM
    """单个员工执行任务（供线程池调用）"""
    spec = SUBAGENT_SPECS[agent_type]
    runner = AgentRunner(HelloAgentsLLM(), agent_name=agent_type)
    sub_tools = BaseTool().get_tools_by_names(spec["tools"])
    sub_history = [
        {"role": "system", "content": spec["system_prompt"]},
        {"role": "user", "content": task},
    ]
    return runner.run(sub_history, sub_tools, max_turns=spec['max_turns'])

# 当LLM一次发出多个dispatch_subagent时，在agent_runner李并行执行
def _execute_tools_parallel(tool_calls: list) -> list:
    """并行执行多个工具调用"""
    results = []

    # 只有多个dispatch_subagent才并行，其他工具仍串行
    subagent_calls  = [tc for tc in tool_calls if tc.function.name == 'dispatch_subagent']
    other_calls = [tc for tc in tool_calls if tc.function.name != 'dispatch_subagent']

    # 1. 其他工具先串行
    for tc in other_calls:
        output = execute_basic_tool(tc)
        results.append({"role": "tool", "tool_call_id": tc.id, "content": output})

    # 子Agent并行执行
    if len(subagent_calls) > 1:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(execute_basic_tool, tc): tc for tc in subagent_calls
            }
            for future in as_completed(futures):
                tc = futures[future]
                output = future.result()
                results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": output
                })
    else:
        for tc in subagent_calls:
            output = execute_basic_tool(tc)
            results.append({"role": "tool", "tool_call_id": tc.id, "content": output})
    return results

class DispatchSubagentTool(BaseTool):
    """加载技能 - 加载指定技能的详细知识内容，在回答相关问题前调用"""

    name = "dispatch_subagent"
    description = (
                "派遣一个AI员工去单独办事。"
                "适用于：需求分析、代码开发、功能测试等专业任务。"
                "员工会独立完成任务并返回总结报告。"
                "若多个任务互不依赖，可在同一回复中发出多个 dispatch_subagent 并发执行。"
                "请在 task 中写清要做什么、希望返回什么格式的总结。"
            )


    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "交代给员工的任务说明，要具体明确"
                    },
                    "agent_type": {
                        "type": "string",
                        "enum": SUBAGENT_TYPE_OPTIONS,
                        "description": (
                            "员工类型选择："
                            "product_manager：产品经理（需求分析）。"
                            "program_engineer：开发工程师（代码开发）。"
                            "test_engineer：测试工程师（功能测试）。"
                        )
                    },
                    "purpose": {
                        "type": "string",
                        "description": "一句话用途标签（可选），仅用于终端打印"
                    }
                },
                "required": ["task", "agent_type"]
        }

    def execute(self, tool_call) -> str:
        from myagents.agent_runner import AgentRunner
        from myagents.core.llm_client import HelloAgentsLLM
        import json
        args = json.loads(tool_call.function.arguments)
        # 子agent名字
        agent_type = args['agent_type']
        # 子agent任务
        task = args['task']
        runner = AgentRunner(HelloAgentsLLM(), agent_name=agent_type)

        """运行一个子代理，让它独立完成任务"""
        if agent_type not in SUBAGENT_SPECS:
            return f"错误：未知的员工类型 '{agent_type}'。可用类型：{', '.join(SUBAGENT_SPECS.keys())}"
        spec = SUBAGENT_SPECS[agent_type]
        print(f"\n{'='*60}")
        print(f"🚀 派遣 {spec['title']} 执行任务")
        print(f"任务内容: {task[:100]}...")
        print(f"{'='*60}\n")

        sub_tools = self.get_tools_by_names(spec['tools'])
        sub_history = [
            {"role": "system", "content": spec["system_prompt"]},
            {"role": "user", "content": task},
        ]

        final_result = runner.run(sub_history, sub_tools, max_turns=spec['max_turns'])

        print(f"{'=' * 60}")
        print(f"✅ {spec['title']} 返回结果")
        print(f"{'=' * 60}\n")
        return final_result






