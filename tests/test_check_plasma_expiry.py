from agent_hemo.tools.check_plasma_expiry_tool import CheckPlasmaExpiryTool
from tests.conftest import make_tool_call

def test_check_plasma_expiry():
    tool = CheckPlasmaExpiryTool()
    result = tool.execute(make_tool_call("check_plasma_expiry", {
        "csv_path": "data/bag_info.csv",
        "date": "2026-06-18"
    }))
    print(result)
    assert "临期血浆信息" in result