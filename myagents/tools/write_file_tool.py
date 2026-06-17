from pathlib import Path

from myagents.tools.base_tool import BaseTool
from myagents.utils.sandbox import is_path_allowed
from myagents.config import PROJECT_ROOT


class WriteFileTool(BaseTool):
    """写入文件 - 向指定路径写入文件内容，如果目录不存在会自动创建"""

    name = "write_file"
    description = "向指定路径写入文件内容，如果目录不存在会自动创建"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"}
                },
                "required": ["path", "content"]
            }

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        path = args["path"]
        content = args["content"]
        print(f"[写入文件]: {path}")

        if not is_path_allowed(path):
            return (
                f"安全限制：不允许访问项目目录外的路径 '{path}'。"
                f"工作区根目录: {PROJECT_ROOT}"
            )

        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"写入成功: {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

