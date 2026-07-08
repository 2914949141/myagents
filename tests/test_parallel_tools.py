# tests/test_parallel_tools.py
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import time

def test_parallel_faster_than_serial():
    """两个 dispatch_subagent 并行时，总耗时应小于串行两倍"""
    def slow_execute(tool_call):
        time.sleep(0.5)
        return "done"

    tc1 = SimpleNamespace(id="1", function=SimpleNamespace(name="dispatch_subagent", arguments="{}"))
    tc2 = SimpleNamespace(id="2", function=SimpleNamespace(name="dispatch_subagent", arguments="{}"))

    with patch("agent_hemo.tools.dispatch_subagent_tool.execute_basic_tool", side_effect=slow_execute):
        t0 = time.time()
        from agent_hemo.tools.dispatch_subagent_tool import _execute_tools_parallel
        results = _execute_tools_parallel([tc1, tc2])
        elapsed = time.time() - t0

    assert len(results) == 2
    assert elapsed < 0.9  # 并行约 0.5s，串行约 1.0s