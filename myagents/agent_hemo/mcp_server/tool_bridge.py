"""BaseTool 注册表 -> MCP 工具桥接 """

import json
from types import SimpleNamespace
from typing import Any

from mcp.server.fastmcp import FastMCP

# 触发所有工具注册到 BaseTool._registry

from agent_hemo.tools import BaseTool

# 白名单: 质保路适合在IDE 里用业务工具
MCP_TOOL_NAMES = [
    "check_plasma_expiry",
    "rag_search",
    "generate_blood_report",
]
_JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}

def _make_tool_call(name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id="mcp-call",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )

def _run_base_tool(tool_name: str, arguments: dict) -> str:
    tool_cls = BaseTool._registry.get(tool_name)
    if not tool_cls:
        return f"找不到工具：{tool_name}"
    # 去掉MCP传入的None (可选参数未填时)
    clean = {k: v for k, v in arguments.items() if v is not None}
    tool_call = _make_tool_call(tool_name, clean)
    return tool_cls().execute(tool_call)

def _build_handler(tool_cls: type[BaseTool]):
    """按 BaseTool.get_parameters() 构建 MCP 工具处理函数"""
    schema = tool_cls.get_parameters()
    properties: dict[str, Any] = schema.get("properties", {})
    required = set(schema.get("required", []))
    tool_name = tool_cls.name

    def handler(**kwargs) -> str:
        return _run_base_tool(tool_name, kwargs)

    handler.__name__ = tool_name
    handler.__doc__ = tool_cls.description

    annotations: dict[str, Any] = {"return": str}
    for param_name, param_info in properties.items():
        py_type = _JSON_TYPE_MAP.get(param_info.get("type", "string"), str)
        if param_name not in required:
            annotations[param_name] = py_type | None
        else:
            annotations[param_name] = py_type
    handler.__annotations__ = annotations
    return handler

def register_tools(mcp: FastMCP) -> list[str]:
    """把白名单里的BaseTool 注册为MCP tools 返回已注册工具名"""
    registered: list[str] = []
    for name in MCP_TOOL_NAMES:
        tool_cls = BaseTool._registry.get(name)
        if not tool_cls:
            raise ValueError(f"MCP 白名单工具未注册: {name}，请确认 agent_hemo.tools 已 import")
        handler = _build_handler(tool_cls)
        mcp.add_tool(handler, name=name, description=tool_cls.description)
        registered.append(name)
    return registered
