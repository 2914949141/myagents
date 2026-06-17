"""Base tool class"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import time

class BaseTool(ABC):
    """所有工具的基类"""
    
    name: str = "base_tool"
    description: str = "基础工具"

    # 全局注册表：key = 属性值，value = 类
    _registry = {}
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行工具，子类必须实现"""
        pass

        # 子类一创建，自动注册到注册表

    def __init_subclass__(cls, **kwargs):
        # 每个子类必须定义一个唯一标识属性，比如 name
        if hasattr(cls, "name"):
            BaseTool._registry[cls.name] = cls

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """转换为字典格式（用于OpenAI API）"""
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.get_parameters()
            }
        }

    @classmethod
    def get_parameters(cls) -> Dict[str, Any]:
        """返回参数定义，子类可覆盖"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"

    @classmethod
    def get_all_tools(cls):
        return [tool_cls.to_dict() for tool_cls in cls._registry.values()]

    def get_tools_by_names(self, names: list[str]) -> list:
        """按工具名白名单过滤"""
        all_tools = self.get_all_tools()
        allowed_tools = [tool for tool in all_tools if tool['function']['name'] in names]
        return allowed_tools


def execute_basic_tool(tool_call) -> str:
    import json
    from myagents.utils.logger import AgentTracer
    tracer = AgentTracer()
    
    t1 = time.time()
    tracer.on_tool_start(
        tool_call.function.name, 
        tool_call.function.arguments,
    )

    """
    执行工具调用
    只需要传入 tool_call 对象（包含 function.name）
    自动找到类 → 执行 execute()
    """
    tool_name = tool_call.function.name
    tool_cls = BaseTool._registry.get(tool_name)
    
    if not tool_cls:
        raise ValueError(f"找不到工具：{tool_name}")
    
    # 实例化并执行
    try:
        tool = tool_cls()
        output = tool.execute(tool_call)
        tracer.on_tool_end(
            tool_call.function.name, 
            output, 
            (time.time() - t1) * 1000
        )
        return output
    except json.JSONDecodeError:
        tracer.on_tool_end(
            tool_call.function.name, 
            f"错误：工具 '{tool_name}' 的参数不是合法 JSON", 
            (time.time() - t1) * 1000
        )
        return f"错误：工具 '{tool_name}' 的参数不是合法 JSON"
    except Exception as e:
        tracer.on_tool_end(
            tool_call.function.name, 
            f"工具执行失败: {str(e)}", 
            (time.time() - t1) * 1000
        )
        return f"工具执行失败: {e}"