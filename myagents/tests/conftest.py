import json
from types import SimpleNamespace
from pathlib import Path
import sys


# 把claude-agent_examples 加入到sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_tool_call(name: str, arguments: dict):
    """构造一个假的tool_call对象，供工具execute()使用"""
    return SimpleNamespace(
        id="test-call-1",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False)
        ),
       )