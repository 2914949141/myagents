from pathlib import Path

from agent_hemo.tools.base_tool import BaseTool
from agent_hemo.memory.memory_store import MemoryStore


class ReadMemoryTool(BaseTool):
    """读取长期记忆 - 从长期记忆中读取信息，当用户问'你还记得XXX吗'时调用"""

    name = "read_memory"
    description = "从长期记忆中读取信息，当用户问'你还记得XXX吗'时调用"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要查询的内容关键词"
                    }
                },
                "required": ["query"]
            }

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        query = args['query']
        print(f"[查询记忆]: {query}")
        key_memory = MemoryStore().read_key_memory()
        today_memory = MemoryStore().read_today_episode()

        # 简单的关键词匹配（实际项目中可以用向量搜索）
        relavant_info = []
        if query.lower() in key_memory.lower():
            relavant_info.append(f"【长期记忆中找到相关内容】:\n{key_memory}")
        if today_memory and query.lower() in today_memory.lower():
            relavant_info.append(f"【今天的情景记忆】:\n{today_memory}")

        if relavant_info:
            return "\n".join(relavant_info)
        else:
            return f"❌ 未在记忆中找到关于 '{query}' 的信息"
