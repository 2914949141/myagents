from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户问题")
    session_id: str | None = Field(None, description="会话ID, 不传则新建")

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    sources: list[str] = []

class ReportRequest(BaseModel):
    csv_path: str= Field(
        default="data/daily_collection_2025-06-18.csv", 
        description="相对项目根目录的 CSV 路径"
    )
    report_type: Literal["daily", "weekly"] = Field(
        default="daily", description="报告类型: daily (日报) 或 weekly (周报)")
    title: str = "采供血日报"

class ReportResponse(BaseModel):
    message: str
    report_path: str | None = None

class AlertsResponse(BaseModel):
    date: str
    csv_path: str
    alerts: dict[str, int]

class AlertsRunRequest(BaseModel):
    csv_path: str = Field(default="data/bag_info.csv")
    date: str | None = Field(None, description="统计日期，默认今天")
    send_notify: bool = Field(default=True, description="是否发 Webhook")

class AlertsRunResponse(BaseModel):
    date: str
    csv_path: str
    alerts: dict[str, int]
    total: int
    report_path: str
    notify: dict

class AlertWorkflowStartRequest(BaseModel):
    csv_path: str = Field(default="data/bag_info.csv")
    date: str | None = Field(None, description="统计日期，默认今天")
    send_notify: bool = Field(default=True, description="是否发 Webhook")
    require_human: bool = Field(default=True, description="通知成功后是否需要人工确认")
    thread_id: str | None = Field(None, description="可选，自定义 thread_id")

class AlertWorkflowStartResponse(BaseModel):
    thread_id: str
    status: str
    pending: bool
    next_nodes: list[str]
    state: dict

class AlertWorkflowConfirmRequest(BaseModel):
    decision: Literal["approved", "rejected"]

class AlertWorkflowStatusResponse(BaseModel):
    thread_id: str
    status: str
    pending: bool
    next_nodes: list[str]
    state: dict