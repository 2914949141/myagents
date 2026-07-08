"""MCP Server：通过 tool_bridge 暴露 BaseTool。"""

import json
from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP
from agent_hemo.mcp_server.tool_bridge import register_tools

mcp = FastMCP("agent-hemo")
register_tools(mcp)


# def _make_tool_call(name: str, arguments: dict):
#     """构造 CheckPlasmaExpiryTool.execute() 需要的 tool_call 对象。"""
#     return SimpleNamespace(
#         id="mcp-call",
#         function=SimpleNamespace(
#             name=name,
#             arguments=json.dumps(arguments, ensure_ascii=False),
#         ),
#     )
# @mcp.tool()
# def check_plasma_expiry(csv_path: str, date: str) -> str:
#     """检查临期血浆信息。
#     适用于检查临期血浆并及时提醒处理。
#     csv_path 为相对项目根目录的路径，如 data/bag_info.csv。
#     date 为统计日期，格式 YYYY-MM-DD，如 2026-06-18。
#     """
#     tool = CheckPlasmaExpiryTool()
#     tool_call = _make_tool_call(
#         "check_plasma_expiry",
#         {"csv_path": csv_path, "date": date},
#     )
#     return tool.execute(tool_call)

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()