"""Command execution tool for running shell commands"""

import subprocess

from myagents.config import COMMAND_TIMEOUT
from myagents.tools.base_tool import BaseTool
from myagents.utils.sandbox import confirm_dangerous_action

class CommandTool(BaseTool):
    """命令行执行工具 - 在终端执行 shell 命令并返回输出"""
    
    name = "run_command"
    description = "在终端执行一条 shell 命令并返回输出"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的shell命令"
                }
            },
            "required": ["command"]
        }
    
    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        command = args['command']
        """
        执行命令
        
        Args:
            command: 要执行的 shell 命令
            
        Returns:
            命令的输出结果（stdout 或 stderr）
        """

        # is_allowed, reason = validate_command(command)
        # if not is_allowed:
        #     print(f"[安全拦截]: {reason}")
        #     AgentTracer().on_security_block("run_command", reason) 
        #     return f"安全限制：{reason}"

        if not confirm_dangerous_action("执行命令", command):
            return "用户拒绝了命令执行"

        print(f"[执行命令]: {command}")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                encoding="utf-8",    # 显式指定 UTF-8
                errors="replace",   # 个别字符解不了时用 代替，不崩溃
                timeout=COMMAND_TIMEOUT
            )
            output = result.stdout or result.stderr
            print(f"[命令输出]: {output}")
            return output
        except subprocess.TimeoutExpired:
            error_msg = f"命令执行超时（超过{COMMAND_TIMEOUT}秒）: {command}"
            print(f"[错误]: {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"命令执行失败: {str(e)}"
            print(f"[错误]: {error_msg}")
            return error_msg
