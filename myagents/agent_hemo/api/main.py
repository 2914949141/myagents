import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.staticfiles import StaticFiles

from agent_hemo.api.schemas import ChatRequest, ChatResponse, ReportRequest, ReportResponse, AlertsResponse, AlertsRunRequest, AlertsRunResponse, AlertWorkflowStartRequest, AlertWorkflowStartResponse, AlertWorkflowStatusResponse, AlertWorkflowConfirmRequest
from agent_hemo.settings import API_KEY, PROJECT_ROOT, STATIC_DIR, UTC8, resolve_project_path
from agent_hemo.tools.blood_report_tool import BloodReportTool
from agent_hemo.tools.check_plasma_expiry_tool import CheckPlasmaExpiryTool
from agent_hemo.api.alerts_pipeline import run_alert_pipeline
from agent_hemo.api.sessions import session_manager
from agent_hemo.api.tool_helpers import parse_report_path, make_tool_call
from fastapi.responses import StreamingResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent_hemo.workflows.alert_graph import start_alert_workflow, confirm_alert_workflow, get_workflow_status
from agent_hemo.api.auth import router as auth_router, verify_auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json

os.chdir(PROJECT_ROOT)

from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[RAG] 预热中...")
    # from agent_hemo.tools.rag_tool import RagTool
    # store = RagTool().get_faiss_store()
    # store.search("预热", top_k=1)   # 顺带加载 Reranker
    print("[RAG] 预热完成")
    
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        lambda: run_alert_pipeline(send_notify=True),
        "cron",
        hour=16,
        minute=3,
    )
    scheduler.start()
    print("scheduler start")
    yield
    print("scheduler shutdown")
    scheduler.shutdown()

app = FastAPI(
    title="血站智能助手 API",
    description="问答 / 日报 / 临期血浆",
    version="0.1.0",
    lifespan=lifespan
)
app.include_router(auth_router)
# 限流器
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")



def verify_api_key(x_api_key: str | None = Header(None)):
    """简单鉴权: .env 里没配 API_KEY 则跳过"""
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key 错误")

@app.get("/health")
@limiter.limit("10/minute")
def health(request: Request):
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
def chat(request: Request, body: ChatRequest, user: str = Depends(verify_auth)):
    session_id, agent = session_manager.get_or_create(body.session_id)
    reply, sources = agent.chat(body.message, quiet=True)
    return ChatResponse(session_id=session_id, reply=reply, sources=sources)

@app.post("/chat/stream")
@limiter.limit("10/minute")
def chat_stream(request: Request, body: ChatRequest, user: str = Depends(verify_auth)):
    session_id, agent = session_manager.get_or_create(body.session_id)

    def event_gen():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        for event in agent.chat_stream(body.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.post("/report", response_model=ReportResponse)
def generate_report(request: ReportRequest, user: str = Depends(verify_auth)):
    tool = BloodReportTool()
    tc = make_tool_call(
        "generate_blood_report", 
        {
            "csv_path": request.csv_path,
            "report_type": request.report_type,
            "title": request.title,
        },
    )

    message = tool.execute(tc)

    if message.startswith(("文件不存在", "安全限制", "CSV为空")):
        raise HTTPException(status_code=400, detail=message)

    return ReportResponse(
        message=message,
        report_path=parse_report_path(message),
    )

@app.post("/alerts", response_model=AlertsResponse)
def get_alerts(
    csv_path: str = "data/bag_info.csv",
    date: str = datetime.now(UTC8).strftime("%Y-%m-%d"),
    user: str = Depends(verify_auth),
):
    tool = CheckPlasmaExpiryTool()
    path = resolve_project_path(csv_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"文件不存在: {csv_path}")

    import csv
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    
    alerts = tool._get_expiry_count(rows, date)
    return AlertsResponse(date=date, csv_path=csv_path, alerts=alerts)

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, user: str = Depends(verify_auth)):
    if not session_manager.delete(session_id):
        raise HTTPException(status_code=404, detail=f"session not found")
    return {"ok": True}


@app.post("/alerts/run", response_model=AlertsRunResponse)
def run_alerts(request: AlertsRunRequest, user: str = Depends(verify_auth)):
    try:
        result = run_alert_pipeline(
            csv_path=request.csv_path,
            cur_date=request.date,
            send_notify=request.send_notify,
        )
    except FileNotFoundError  as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AlertsRunResponse(**result)

@app.post("/alerts/workflow/start", response_model=AlertWorkflowStartResponse)
def start_alerts_workflow(request: AlertWorkflowStartRequest, user: str = Depends(verify_auth)):
    try:
        result = start_alert_workflow(
            csv_path=request.csv_path,
            date=request.date,
            send_notify=request.send_notify,
            require_human=request.require_human,
            thread_id=request.thread_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AlertWorkflowStartResponse(**result)

@app.post("/alerts/workflow/{thread_id}", response_model=AlertWorkflowStatusResponse)
def get_alerts_workflow_status(thread_id: str, user: str = Depends(verify_auth)):
    result = get_workflow_status(thread_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"thread_id 不存在: {thread_id}")
    return AlertWorkflowStatusResponse(**result)

@app.post("/alerts/workflow/{thread_id}/confirm", response_model=AlertWorkflowStatusResponse)
def confirm_alerts_workflow(thread_id: str, request: AlertWorkflowConfirmRequest, user: str = Depends(verify_auth)):
    try:
        result = confirm_alert_workflow(thread_id, request.decision)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AlertWorkflowStatusResponse(**result)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_hemo.api.main:app", host="0.0.0.0", port=8000, reload=True)