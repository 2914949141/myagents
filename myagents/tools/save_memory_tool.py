from pathlib import Path

from myagents.tools.base_tool import BaseTool
from myagents.memory.memory_store import MemoryStore


class SaveMemoryTool(BaseTool):
    """保存长期记忆 - 将重要信息保存到长期记忆中，当用户说'记住XXX'时调用"""

    name = "save_to_memory"
    description = "将重要信息保存到长期记忆中，当用户说'记住XXX'时调用"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "info": {
                        "type": "string",
                        "description": "需要记住的信息内容"
                    }
                },
                "required": ["info"]
            }

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        info = args["info"]
        print(f"[保存到记忆]: {info}")
        MemoryStore().append_key_memory(info)
        # 同时保存到情景记忆
        MemoryStore().append_episode(f"**保存的记忆**: {info}")
        return f"✅ 已将以下信息保存到长期记忆:\n{info}"
