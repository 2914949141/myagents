import pytest

from agent_hemo.api.alerts_pipeline import (
    collect_expiring_bags,
    load_bag_rows,
    run_alert_pipeline,
)
from agent_hemo.settings import PROJECT_ROOT, WEBHOOK_URL


def test_collect_expiring_bags():
    rows = load_bag_rows("data/bag_info.csv")
    details = collect_expiring_bags(rows, "2026-06-18")
    assert isinstance(details, list)
    for item in details:
        assert "station_name" in item
        assert "bag_no" in item


def test_run_pipeline_no_webhook(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "")
    result = run_alert_pipeline(
        csv_path="data/bag_info.csv",
        cur_date="2026-06-18",
        send_notify=False,
    )
    assert result["report_path"].startswith("data/reports/alerts-")
    report = PROJECT_ROOT / result["report_path"]
    assert report.exists()
    assert "临期血浆预警报告" in report.read_text(encoding="utf-8")
    assert result["notify"]["sent"] is False


@pytest.mark.integration
def test_run_alert_pipeline_send_dingtalk():
    """
    本地手动跑告警流水线并发送钉钉（不经过 API POST）。

    用法：
      cd D:\\pythonfile\\claude-agent-examples
      pytest tests/test_alerts_pipeline.py::test_run_alert_pipeline_send_dingtalk -s -m integration

    需在 .env 配置 WEBHOOK_URL；若机器人启用了加签，再配 WEBHOOK_SECRET 或 DINGTALK_SECRET。
    """
    if not WEBHOOK_URL.strip():
        pytest.skip("未配置 WEBHOOK_URL，跳过钉钉发送测试")

    result = run_alert_pipeline(
        csv_path="data/bag_info.csv",
        cur_date="2026-06-18",
        send_notify=True,
    )

    print("\n--- 流水线结果 ---")
    print(f"报告: {result['report_path']}")
    print(f"汇总: {result['alerts']}")
    print(f"合计: {result['total']} 袋")
    print(f"通知: {result['notify']}")

    assert result["report_path"].startswith("data/reports/alerts-")
    assert (PROJECT_ROOT / result["report_path"]).exists()
    assert result["notify"].get("sent") is True, result["notify"]
