from tests.conftest import make_tool_call
from agent_hemo.tools.plan_tool import PlanTool
import pytest

@pytest.fixture(autouse=True)
def reset_plans():
    """每个测试前都清空plan状态"""
    PlanTool.PLANS = []
    yield
    PlanTool.PLANS = []

def test_plan_update_success():
    tool = PlanTool()
    result = tool.execute(make_tool_call("plan", {
    "plan": [
        {"id": 1, "content": "分析需求", "status": "in_progress"},
        {"id": 2, "content": "写代码", "status": "pending"}
        ]
    }))
    assert "plan updated" in result
    assert len(PlanTool.PLANS) == 2
    assert PlanTool.PLANS[0]["status"] == "in_progress"

def test_plan_reject_multiple_in_progress():
    tool = PlanTool()
    result = tool.execute(make_tool_call("plan", {
         "plan": [
            {"id": 1, "content": "A", "status": "in_progress"},
            {"id": 2, "content": "B", "status": "in_progress"},
        ]
    }))
    assert "Error" in result


def test_plan_persists_across_instances():
    """验证类变量PlanTool.PLANS 跨实例持久化"""
    PlanTool().execute(make_tool_call("plan", {
        "plan": [{"id": 1, "content": "任务1", "status": "pending"}]
    }))
    result = PlanTool().execute(make_tool_call("plan", {
        "plan": [{"id": 1, "content": "任务1", "status": "completed"}]
    }))
    assert PlanTool.PLANS[0]["status"] == "completed"