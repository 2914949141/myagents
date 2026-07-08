from agent_hemo.tools.base_tool import BaseTool
from agent_hemo.utils.sandbox import is_path_allowed
from agent_hemo.settings import PROJECT_ROOT, resolve_project_path


class ReadFileTool(BaseTool):
    """读取文件工具 - 读取指定路径的文件内容"""

    name = "read_file"
    description = "读取指定路径的文件内容"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            }

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        path = args["path"]
        print(f"[读取文件]: {path}")

        if not is_path_allowed(path):
            return (
                f"安全限制：不允许访问项目目录外的路径 '{path}'。"
                f"工作区根目录: {PROJECT_ROOT}"
            )

        try:
            return resolve_project_path(path).read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading {path}: {e}"

