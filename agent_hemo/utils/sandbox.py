from pathlib import Path

from agent_hemo.settings import PROJECT_ROOT

# --命令白名单---------------
ALLOWED_COMMANDS = {
    "python", "pip", "dir", "curl", "find", "grep",
    "echo", "cd", "tree", "where", "ls",
}

# 明确禁止的危险命令片段
BLOCKED_PATTERNS = [
    "rm ", "del ", "format", "shutdown", "reboot",
    "rmdir", "rd /s", "mkfs", "dd ", ">nul",
    "reg ", "net user", "powershell -enc",
]


def is_path_allowed(path: str) -> bool:
    """检查路径是否在项目工作区内"""
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        resolved = p.resolve()
        return str(resolved).startswith(str(PROJECT_ROOT))
    except Exception:
        return False


def validate_command(command: str) -> tuple[bool, str]:
    """检查命令是否安全，返回（是否允许，原因说明）"""
    cmd_lower = command.strip().lower()

    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return False, f"禁止性质含有: '{pattern}'的命令"

    base_cmd = command.strip().split()[0].lower() if command.strip() else ""
    base_cmd = Path(base_cmd).stem.lower()

    if base_cmd not in ALLOWED_COMMANDS:
        return False, f"命令'{base_cmd}'不在白名单内.允许：{', '.join(ALLOWED_COMMANDS)}"
    return True, "OK"


def confirm_dangerous_action(action: str, details: str) -> bool:
    """危险操作前请求用户确认"""
    allowed, reason = validate_command(details)
    if not allowed:
        print(f"[安全拦截]: {reason}")
        return False

    print(f"\n⚠️  Agent 请求执行: {action}")
    print(f"   详情: {details}")
    answer = input("   允许执行吗？(y/n): ").strip().lower()
    return answer in ("y", "对", "允许", "执行", "yes", "是")
