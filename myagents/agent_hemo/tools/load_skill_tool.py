from .base_tool import BaseTool
import urllib.request
from html.parser import HTMLParser
import re
import sys
import os

from agent_hemo.utils.skill_loader import SkillLoader
from agent_hemo.settings import SKILLS_DIR

SKILL_LOADER = SkillLoader(SKILLS_DIR)

class LoadSkillTool(BaseTool):
    """加载技能 - 加载指定技能的详细知识内容，在回答相关问题前调用"""

    name = "load_skill"
    description = "加载指定技能的详细知识内容，在回答相关问题前调用"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "技能名称，必须是系统提示中列出的可用技能之一"
                    }
                },
                "required": ["skill_name"]
        }

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        skill_name = args["skill_name"]
        print(f"[加载技能]: {skill_name}")
        content = SKILL_LOADER.get_content(skill_name)
        return content
