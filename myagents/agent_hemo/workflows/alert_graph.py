"""临期血浆告警 LangGraph 工作流 — Step 1: detect → report"""
from __future__ import annotations
import sqlite3
import uuid
from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from agent_hemo.workflows.alert_state import AlertState
from datetime import datetime
from typing import Literal

from agent_hemo.api.alerts_pipeline import (
    load_bag_rows, 
    collect_expiring_bags, 
    summarize_by_station, 
    render_alert_markdown,
    save_report,
    send_webhook,
)
from agent_hemo.settings import (
    ALERT_CSV_PATH,
    ALERT_WARNING_DAYS,
    UTC8,
    PROJECT_ROOT,
    WORKFLOW_CHECKPOINT_DB,
)

# 进程内单例 checkpointer (学习用 MemorySaver; 生产可换 SqliteSaver)
_CHECKPOINTER: SqliteSaver | None = None
_SQLITE_CONN: sqlite3.Connection | None = None
_COMPLIED_APP = None

def get_checkpointer() -> SqliteSaver:
    global _CHECKPOINTER, _SQLITE_CONN
    if _CHECKPOINTER is None:
        WORKFLOW_CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        _SQLITE_CONN = sqlite3.connect(
            str(WORKFLOW_CHECKPOINT_DB),
            check_same_thread=False,
        )
        _CHECKPOINTER = SqliteSaver(_SQLITE_CONN)
    return _CHECKPOINTER

def delect_node(state: AlertState) -> AlertState:
    """读取 CSV, 统计临期血浆明细与各站汇总。"""
    csv_path = state.get("csv_path") or ALERT_CSV_PATH
    cur_date = state.get("date") or datetime.now(UTC8).strftime("%Y-%m-%d")
    warning_days = state.get("warning_days") or ALERT_WARNING_DAYS

    rows = load_bag_rows(csv_path)
    details = collect_expiring_bags(rows, cur_date, warning_days)
    summary = summarize_by_station(details)
    total = sum(summary.values())

    return {
        "date": cur_date,
        "csv_path": csv_path,
        "warning_days": warning_days,
        "details": details,
        "summary": summary,
        "total": total,
    }

def report_node(state: AlertState) -> AlertState:
    """渲染 Markdown 并写入 reports/alerts-YYYY-MM-DD.md。"""
    cur_date = state["date"]
    csv_path = state["csv_path"]
    warning_days = state.get("warning_days", ALERT_WARNING_DAYS)
    summary = state.get("summary") or {}
    details = state.get("details") or []

    markdown = render_alert_markdown(cur_date, csv_path, summary, details, warning_days)
    report_path = save_report(markdown, cur_date)

    return {
        "markdown": markdown,
        "report_path": report_path.relative_to(PROJECT_ROOT).as_posix(),
    }

def notify_node(state: AlertState) -> AlertState:
    """发送钉钉 / Webhook 通知。"""
    markdown = state.get("markdown") or ""
    summary = state.get("summary") or {}
    cur_date = state["date"]

    try:
        notify_result = send_webhook(markdown, summary, cur_date)
    except Exception as e:
        notify_result = {"sent": False, "reason": str(e)}

    return {"notify_result": notify_result}

def skip_notify_node(state: AlertState) -> AlertState:
    """跳过通知，并记录原因。"""
    if not state.get("send_notify", True):
        reason = "send_notify=false"
    elif state.get("total", 0) <= 0:
        reason = "no_expiring_bags"
    else:
        reason = "skipped"
    
    return {"notify_result": {"sent": False, "reason": reason}}

def wait_human_node(state: AlertState) -> AlertState:
    """ 通知已发，进入待质控确认状态 """
    return {
        "workflow_status": "pending_human",
        "human_decision": state.get("human_decision", "")
    }

def follow_up_node(state: AlertState) -> AlertState:
    """ 质控确认后 生成回访建议 """
    decision = state.get("human_decision", "")
    summary = state.get("summary") or {}

    if decision == "approved":
        lines = [
            f"- {station}: 建议优先安排 {count} 袋出库或回访"
            for station, count in sorted(summary.items(), key=lambda x: -x[1])
        ]
        notes = "质控已确认。\n回访建议: \n" + ("\n".join(lines) if lines else "- 无临期袋")
        status = "completed"
    elif decision == "rejected":
        notes = "质控已驳回。请复核临期数据与现场库存后重新发起告警。"
        status = "rejected"
    else:
        notes = "未收到有效确认决策。"
        status = "rejected"

    return {
        "workflow_status": status,
        "follow_up_notes": notes,
    }

def route_after_report(state: AlertState) -> Literal["notify", "skip_notify"]:
    """report 之后：有临期且允许通知才走 notify。"""
    if not state.get("send_notify", True):
        return "skip_notify"
    if state.get("total", 0) <= 0:
        return "skip_notify"
    return "notify"

def route_after_notify(state: AlertState) -> Literal["wait_human", "end"]:
    """ 通知成功且有临期 -> 进入人工确认; 否则直接结束 """
    if not state.get("require_human", True):
        return "end"
    if state.get("total", 0) <= 0:
        return "end"
    if not state.get("notify_result", {}).get("sent"):
        return "end"
    return "wait_human"

def build_alert_graph(*, checkpointer=None):
    """构建并编译 detect -> report 图 """
    graph = StateGraph(AlertState)
    graph.add_node("detect", delect_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)
    graph.add_node("skip_notify", skip_notify_node)
    graph.add_node("wait_human", wait_human_node)
    graph.add_node("follow_up", follow_up_node)

    graph.set_entry_point("detect")
    graph.add_edge("detect", "report")
    graph.add_conditional_edges(
        "report", 
        route_after_report,
        {
            "notify": "notify",
            "skip_notify": "skip_notify",
        }
    )
    graph.add_conditional_edges(
        "notify",
        route_after_notify,
        {
            "wait_human": "wait_human",
            "end": END,
        }
    )
    graph.add_edge("skip_notify", END)
    graph.add_edge("wait_human", "follow_up")
    graph.add_edge("follow_up", END)
    return graph.compile(
        checkpointer=checkpointer or get_checkpointer(),
        interrupt_before=["follow_up"],
    )

def get_compiled_app():
    """复用同一个 compiled app + 同一个 checkpointer"""
    global _COMPLIED_APP
    if _COMPLIED_APP is None:
        _COMPLIED_APP = build_alert_graph()
    return _COMPLIED_APP

def _make_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}

def get_workflow_status(thread_id: str) -> dict:
    """查询某 thread 当前状态（供 API 使用）。"""
    app = get_compiled_app()
    config = _make_config(thread_id)
    snapshot = app.get_state(config)
    
    if snapshot.values is None:
        return {
            "thread_id": thread_id,
            "status": "not_found",
            "state": {},
            "pending": False,
            "next_nodes": [],
        }
    state = dict(snapshot.values)
    pending = bool(snapshot.next)
    status = state.get("workflow_status") or ("pending_human" if pending else "completed")
    return {
        "thread_id": thread_id,
        "status": status,
        "state": state,
        "pending": pending,
        "next_nodes": list(snapshot.next),
    }

def start_alert_workflow(
    *,
    date: str | None = None,
    csv_path: str | None = None,
    warning_days: int = ALERT_WARNING_DAYS,
    send_notify: bool = True,
    require_human: bool = True,
    thread_id: str | None = None,
) -> dict:
    """启动工作流；若需人工确认，会在 follow_up 前暂停。"""
    app = get_compiled_app()
    thread_id = thread_id  or f"alert-{uuid.uuid4().hex[:12]}"
    config = _make_config(thread_id)

    initial: AlertState = {
        "csv_path": csv_path or ALERT_CSV_PATH,
        "warning_days": warning_days,
        "send_notify": send_notify,
        "require_human": require_human,
    }
    if date:
        initial["date"] = date
    app.invoke(initial, config)
    return get_workflow_status(thread_id)

def confirm_alert_workflow(
    thread_id: str,
    decision: Literal["approved", "rejected"],
) -> dict:
    """质控确认：写入决策并恢复执行 follow_up。"""
    app = get_compiled_app()
    config = _make_config(thread_id)
    snapshot = app.get_state(config)

    if snapshot.values is None:
        raise ValueError(f"thread_id 不存在: {thread_id}")
    if not snapshot.next:
        raise ValueError(f"thread_id={thread_id} 不在待确认状态")

    app.update_state(config, {"human_decision": decision})
    app.invoke(None, config)
    return get_workflow_status(thread_id)


def run_alert_workflow(
    *,
    date: str | None = None,
    csv_path: str | None = None,
    warning_days: int = ALERT_WARNING_DAYS,
    send_notify: bool = True,
    require_human: bool = True,
    auto_confirm: bool = False,
    human_decision: Literal["approved", "rejected"] = "approved",
    thread_id: str | None = None,
) -> AlertState:
    """测试/脚本入口。auto_confirm=True 时自动走完人工确认。"""
    thread_id = thread_id or f"test-{uuid.uuid4().hex[:8]}"
    start_alert_workflow(
        date=date,
        csv_path=csv_path,
        warning_days=warning_days,
        send_notify=send_notify,
        require_human=require_human,
        thread_id=thread_id,
    )
    status = get_workflow_status(thread_id)
    if status["pending"] and auto_confirm:
        status = confirm_alert_workflow(thread_id, human_decision)
    return status["state"]

if __name__ == "__main__":
    tid = start_alert_workflow(
        date="2026-06-18",
        csv_path="data/bag_info.csv",
        send_notify=False,
    )["thread_id"]
    print("=== Step 3 启动 ===")
    print(get_workflow_status(tid))