from datetime import datetime, date

from agent_hemo.core.llm_client import HelloAgentsLLM
from agent_hemo.utils.skill_loader import SkillLoader
from agent_hemo.settings import SKILLS_DIR, UTC8, MAX_RETRIES
from agent_hemo.memory.memory_store import MemoryStore
from agent_hemo.agent_runner import AgentRunner


class AgentLoop:

    def _build_prompt(self) -> str:
        today = datetime.now(UTC8).strftime('%Y-%m-%d')
        return f"""你是血站智能助手「小杜」，服务于采供血机构工作人员。
            你拥有 PPT 知识库检索能力，知识库包含血液行业培训资料（全血、成分血、血浆、医院联网等）。

            【核心职责】
            - 回答血站/浆站业务知识问题
            - 解读规程、标准、操作流程
            - 协助理解医院联网、发血、献血者管理等业务
            - 用户要求生成采血/献浆日报、周报时，调用 generate_blood_report
            - CSV 数据通常在 data/ 目录
            - 工具生成 Markdown 后，你用自然语言补充简要分析和建议
            - 报表任务不需要 rag_search
            - 当用户问临期血浆信息时，调用 check_plasma_expiry
            
            【报表 / 预警任务 — 与知识问答不同】
            当用户要「采血日报」「献浆日报」「周报」「临期血浆」时：
            1. 禁止调用 rag_search、load_skill、plan、dispatch_subagent
            2. 禁止用 run_command 列目录；CSV 路径规则：
            - 日报：data/daily_collection_YYYY-MM-DD.csv
            - 临期：data/bag_info.csv
            3. 直接调用 generate_blood_report 或 check_plasma_expiry
            4. 需要展示内容时再 read_file 读生成的 reports/*.md


            【知识检索规则 — 最重要】
            1. 用户问业务/规程/标准类问题时，必须先调用 rag_search 检索知识库
            2. 同一轮对话中，同一问题最多调用 2 次 rag_search，不要反复换关键词重复搜索
            3. 基于检索结果回答；若检索无相关内容，如实告知「知识库中未找到」，不要编造
            4. 回答末尾注明参考来源（使用 rag_search 返回的 title，如「来源：血液行业知识-202309 - 第5部分」）
            5. 涉及献血者能否献血的个体判定，只引用规程，并说明「以现场健康征询和医师判定为准」

            【技能使用】
            - 回答血站业务问题前，可先调用 load_skill 加载 blood_station 技能，了解回答规范
            - 当前可用技能：
            {SkillLoader(SKILLS_DIR).get_descriptions()}

            【复杂任务】
            - 仅当用户明确要求写代码、开发系统、多步骤项目时，才使用 plan 和 dispatch_subagent
            - 日常知识问答直接检索 + 回答，无需生成 plan

            【记忆系统】
            - 对话自动记录到 memory/history.jsonl
            - 今天的对话保存在 memory/{today}.md
            - 重要信息保存在 memory/MEMORY.md

            【长期记忆】
            {self.memory_store.read_key_memory()}

            使用中文回复。"""

    def __init__(self):
        self.memory_store = MemoryStore()
        self.agent_runner = AgentRunner(HelloAgentsLLM(), agent_name="main")
        self.history = [{"role": "system", "content": self._build_prompt()}]
        unarchived_history = self.memory_store.load_unarchived_history()
        if unarchived_history:
            print(f"恢复了 {len(unarchived_history)} 条未归档的历史记录")
            self.history.extend(unarchived_history)

    def loop(self):
        print(self._build_prompt())
        while True:
            user_message = input("[用户输入]: ")
            self.chat(user_message, quiet=False)


    def chat(self, user_message: str, quiet: bool = True) -> tuple[str, list[str]]:
        """API 用： 处理单轮用户输入， 返回 Agent 回复"""
        user_message = user_message.strip()
        if not user_message:
            return "", []

        self.memory_store.append_history("user", user_message)
        self.history.append({"role": "user", "content": user_message})
        
        reply, sources = self.agent_runner.run_with_relexion(history=self.history, quiet=quiet)
        return reply, sources

    def chat_stream(self, user_message: str):
        user_message = user_message.strip()
        if not user_message:
            yield {"type": "done", "reply": "", "sources": []}
            return

        self.memory_store.append_history("user", user_message)
        self.history.append({"role": "user", "content": user_message})

        for event in self.agent_runner.run_with_stream(history=self.history):
            yield event