from agent_hemo.tools.blood_report_tool import BloodReportTool
from tests.conftest import make_tool_call

def test_generate_daily_report(tmp_path, monkeypatch):
    # 用fixture CSV 或临时文件
    tool = BloodReportTool()
    result = tool.execute(make_tool_call("generate_blood_report", {
        "csv_path": "data/daily_collection_2025-06-18.csv",
        "report_type": "daily",
        "title": "中心血站2025-06-18 采血日报"
    }))
    assert "报告已生成" in result
    assert "总人次" in result


def test_missing_csv_returns_error():
    tool = BloodReportTool()
    result = tool.execute(make_tool_call("generate_blood_report", {
        "csv_path": "data/daily_collection_2099-01-01.csv",
        "report_type": "daily",
    }))
    assert "文件不存在" in result