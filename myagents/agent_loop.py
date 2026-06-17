from datetime import datetime

from myagents.core.llm_client import HelloAgentsLLM
from myagents.utils.skill_loader import SkillLoader
from myagents.config import SKILLS_DIR, UTC8, MAX_RETRIES
from myagents.memory.memory_store import MemoryStore
from myagents.agent_runner import AgentRunner


class AgentLoop:

    def _build_prompt(self) -> str:
        today = datetime.now(UTC8).strftime('%Y-%m-%d')
        return f"""
        你是一个智能助手小杜，拥有知识库检索能力
        当用户交办比较复杂任务时，先调用 plan 工具制定完整计划
        当用户询问知识性问题时，请先调用 rag_search 工具从知识库中检索相关信息
        然后基于检索结果回答问题，如果检索结果不包含答案，请如实告知用户
        使用中文回复。

        【工作流程】
        1. 当用户交办软件开发或网站任务时，先调用 plan 工具制定完整计划
        2. 按计划顺序派遣合适的员工执行每个步骤：
        - 产品经理：需求分析和产品规划
        - 开发工程师：代码开发和文件创建
        - 测试工程师：功能测试和问题反馈
        3. 每步完成后更新 plan 状态，继续下一步
        4. 所有步骤完成后，向用户汇报最终结果

        【员工调度规则】
        - 同一时间只允许一个任务处于 in_progress 状态
        - 简单任务可直接回答，无需生成 plan
        - 复杂任务必须拆解为多个步骤并派遣员工执行

        【记忆系统使用说明】
        - 系统会自动记录所有对话到 memory/history.jsonl
        - 重要信息会被保存到 memory/MEMORY.md（长期记忆）
        - 今天的对话会保存在 memory/{today}.md（情景记忆）
        - 你可以要求我"记住XXX"，我会将其存入长期记忆
        - 你可以问"你还记得XXX吗"，我会从记忆中检索

        【长期记忆】
        {self.memory_store.read_key_memory()}

        当前可用技能：
        {SkillLoader(SKILLS_DIR).get_descriptions()}"""

    def __init__(self):
        self.memory_store = MemoryStore()
        self.agent_runner = AgentRunner(HelloAgentsLLM(), agent_name="main")
        self.history = [{"role": "system", "content": self._build_prompt()}]
        unarchived_history = self.memory_store.load_unarchived_history()
        if unarchived_history:
            print(f"📚 恢复了 {len(unarchived_history)} 条未归档的历史记录")
            self.history.extend(unarchived_history)

    def loop(self):
        print(self._build_prompt())
        while True:
            user_message = input("[用户输入]: ")
            if not user_message.strip():
                continue
            self.memory_store.append_history("user", user_message)
            self.history.append({"role": "user", "content": user_message})
            self.agent_runner.run_with_relexion(history=self.history, max_retries=MAX_RETRIES)
