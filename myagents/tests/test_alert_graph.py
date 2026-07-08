"""LangGraph 告警工作流测试。"""

import pytest

from agent_hemo.settings import PROJECT_ROOT
from agent_hemo.workflows.alert_graph import (
    build_alert_graph,
    confirm_alert_workflow,
    get_workflow_status,
    run_alert_workflow,
    start_alert_workflow,
)


def test_build_alert_graph_compiles():
    app = build_alert_graph()
    assert app is not None


def test_alert_graph_skip_notify_no_human_step():
    result = run_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=False,
    )
    assert result["report_path"].startswith("data/reports/alerts-")
    assert (PROJECT_ROOT / result["report_path"]).exists()
    assert result["notify_result"]["reason"] == "send_notify=false"


def test_alert_graph_skip_notify_when_no_expiring(monkeypatch):
    monkeypatch.setattr(
        "agent_hemo.workflows.alert_graph.collect_expiring_bags",
        lambda rows, cur_date, warning_days: [],
    )
    result = run_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=True,
    )
    assert result["total"] == 0
    assert result["notify_result"]["reason"] == "no_expiring_bags"


def test_alert_graph_human_confirm_flow(monkeypatch):
    """模拟：通知成功 → 暂停 → 人工批准 → follow_up。"""
    monkeypatch.setattr(
        "agent_hemo.workflows.alert_graph.send_webhook",
        lambda markdown, summary, cur_date: {"sent": True, "status_code": 200},
    )

    started = start_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=True,
        require_human=True,
        thread_id="test-human-flow",
    )
    assert started["pending"] is True
    assert started["status"] == "pending_human"
    assert "follow_up" in started["next_nodes"]

    confirmed = confirm_alert_workflow("test-human-flow", "approved")
    assert confirmed["pending"] is False
    assert confirmed["state"]["workflow_status"] == "completed"
    assert "回访建议" in confirmed["state"]["follow_up_notes"]


def test_alert_graph_auto_confirm(monkeypatch):
    # monkeypatch.setattr(
    #     "agent_hemo.workflows.alert_graph.send_webhook",
    #     lambda markdown, summary, cur_date: {"sent": True},
    # )
    result = run_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=True,
        auto_confirm=True,
    )
    assert result["workflow_status"] == "completed"
    assert result.get("follow_up_notes")


@pytest.mark.integration
def test_alert_graph_send_dingtalk_with_auto_confirm():
    from agent_hemo.settings import WEBHOOK_URL

    if not WEBHOOK_URL.strip():
        pytest.skip("未配置 WEBHOOK_URL")

    result = run_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=True,
        auto_confirm=True,
    )
    assert result["total"] > 0
    assert result["notify_result"].get("sent") is True
    assert result["workflow_status"] == "completed"

def test_workflow_checkpoint_persisted_on_disk(monkeypatch):
    """启动后 checkpoint 应写入 sqlite 文件，且能查到 pending 状态。"""
    monkeypatch.setattr(
        "agent_hemo.workflows.alert_graph.send_webhook",
        lambda markdown, summary, cur_date: {"sent": True, "status_code": 200},
    )
    from agent_hemo.settings import WORKFLOW_CHECKPOINT_DB

    thread_id = "test-sqlite-persist"
    started = start_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=True,
        require_human=True,
        thread_id=thread_id,
    )

    assert WORKFLOW_CHECKPOINT_DB.exists()
    assert started["pending"] is True

    # 模拟新一次查询 仍能从库中读到
    again = get_workflow_status(thread_id)
    assert again["pending"] is True
    assert again["state"]["total"] > 0
    print(f"\nagain: {again}")

    confirm_alert_workflow(thread_id, "approved")
    done = get_workflow_status(thread_id)
    print(f"done: {done}")
    assert done["pending"] is False
    assert done["state"]["workflow_status"] == "completed"