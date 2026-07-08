"""临期告警工作流的状态定义。"""
from typing import TypedDict

class AlertState(TypedDict):
    """LangGraph 各节点共享的状态；total=False 表示字段可分批写入。"""

    # 输入（invoke 时传入，或由 detect 节点补默认）
    date: str
    csv_path: str
    warning_days: int
    send_notify: bool
    require_human: bool

    # detect 节点产出
    summary: dict[str, int]
    details: list[dict]
    total: int

    # report 节点产出
    report_path: str
    markdown: str

    # notify / skip_notify 节点产出
    notify_result: dict

    # wait_human / follow_up
    workflow_status: str  # pending_human | completed | rejected
    human_decision: str  # approved | rejected | ""
    follow_up_notes: str  # 人工确认备注