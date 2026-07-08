"""临期血浆告警流水线：CSV -> Markdown -> Webhook"""

from __future__ import annotations
import csv
from datetime import datetime, date
from pathlib import Path

import hmac
import hashlib
import base64
import time
import urllib.parse

import requests

from agent_hemo.settings import (
    WEBHOOK_URL,
    WEBHOOK_SECRET,
    ALERT_CSV_PATH,
    ALERT_WARNING_DAYS,
    REPORTS_DIR,
    UTC8,
    PROJECT_ROOT,
    resolve_project_path,
)

SHELF_LIFE_DAYS = 365


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def load_bag_rows(csv_path: str) -> list[dict]:
    path = resolve_project_path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {csv_path}")
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("CSV 为空或格式不正确")
    return rows


def _dingtalk_signed_url(webhook_url: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    sign = base64.b64encode(
        hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    sign = urllib.parse.quote_plus(sign)
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp}&sign={sign}"


def collect_expiring_bags(
    rows: list[dict], 
    cur_date: str,
    warning_days: int = ALERT_WARNING_DAYS
) -> list[dict]:
    """返回临期血浆明细列表（每条一袋）"""
    today = _parse_date(cur_date)
    min_age = SHELF_LIFE_DAYS - warning_days
    max_age = SHELF_LIFE_DAYS
    
    details = []
    for row in rows:
        status = (row.get("quality_status") or "").strip()
        if status.startswith("EXP") or status.startswith("QUA"):
            continue
        age_days = (today - _parse_date(row["collect_time"])).days
        if min_age <= age_days <= max_age:
            days_left = SHELF_LIFE_DAYS - age_days
            details.append({
                "station_name": row["station_name"],
                "bag_no": row["bag_no"],
                "collect_time": row["collect_time"],
                "donor_no": row["donor_no"],
                "age_days": age_days,
                "days_left": days_left,
                "quality_status": status,
            })
    return details

def summarize_by_station(details: list[dict]) -> dict[str, int]:
    """各站临期袋数，与 CheckPlasmaExpiryTool._get_expiry_count 结果一致"""
    counts: dict[str, int] = {}
    for item in details:
        station = item["station_name"]
        counts[station] = counts.get(station, 0) + 1
    return counts

def render_alert_markdown(
    cur_date: str,
    csv_path: str,
    summary: dict[str, int],
    details: list[dict],
    warning_days: int = ALERT_WARNING_DAYS
) -> str:
    total = sum(summary.values())
    lines = [
        f"# 临期血浆预警报告",
        "",
        f"> 统计日期：{cur_date} | 数据源：`{csv_path}` | 临期阈值：效期内不足 {warning_days} 天",
        "",
        "## 各站汇总",
        "",
        "| 浆站 | 临期袋数 |",
        "|------|----------|",
    ]
    if summary:
        for station, count in sorted(summary.items(), key=lambda x: -x[1]):
            lines.append(f"| {station} | {count} |")
    else:
        lines.append("| (无) | 0 |")

    lines += [
        "",
        f"**合计：{total} 袋**",
        "",
        "## 明细",
        "",
        "| 浆站 | 袋号 | 采集日期 | 状态 | 库龄(天) | 剩余(天) |",
        "|------|------|----------|------|----------|----------|",
    ]
    for item in sorted(details, key=lambda x: (x["station_name"], x["days_left"])):
        lines.append(
            f"| {item['station_name']} | {item['bag_no']} | {item['collect_time']} "
            f"| {item['quality_status']} | {item['age_days']} | {item['days_left']} |"
        )
    if not details:
        lines.append("| — | — | — | — | — | — |")

    lines += [
        "",
        "## 建议",
        "",
        "- 请各站核对临期血浆，优先安排出库或回访计划",
        "- 以现场质量管理要求为准",
        "",
    ]
    return "\n".join(lines)

def save_report(markdown: str, cur_date: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"alerts-{cur_date}.md"
    out_path.write_text(markdown, encoding="utf-8")
    return out_path

def send_webhook(markdown: str, summary: dict[str, int], cur_date: str) -> dict:
    """发送 Webhook; 未配置 URL 则跳过"""
    if not WEBHOOK_URL:
        return {"sent": False, "error": "未配置 Webhook URL"}
    total = sum(summary.values())
    # 通用 JSON（自己按服务 / 测试用 webhook.site）
    # payload = {
    #     "title": f"临期血浆预警 {cur_date}",
    #     "date": cur_date,
    #     "total": total,
    #     "summary": summary,
    #     "markdown": markdown,
    # }

    # 若是钉钉机器人，可改成:
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"临期血浆预警 {cur_date}",
            "text": f"### 临期血浆预警 {cur_date}\n\n合计 **{total}** 袋\n\n" + "\n".join(
            f"- {k}: {v} 袋" for k, v in summary.items()
        ),
        },
    }
    url = WEBHOOK_URL
    if WEBHOOK_SECRET:
        url = _dingtalk_signed_url(url, WEBHOOK_SECRET)

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json() if resp.content else {}
    if data.get("errcode", 0) != 0:
        return {
            "sent": False,
            "status_code": resp.status_code,
            "errcode": data.get("errcode"),
            "errmsg": data.get("errmsg"),
        }
    return {"sent": True, "status_code": resp.status_code, "errcode": 0}

def run_alert_pipeline(
    cur_date: str | None = None, 
    csv_path: str | None = None,
    send_notify: bool = True,
    warning_days: int = ALERT_WARNING_DAYS,
) -> dict:
    """流水线入口： 读csv -> 统计 -> 写MD -> 可选Webhook"""
    csv_path = csv_path or ALERT_CSV_PATH
    cur_date = cur_date or datetime.now(UTC8).strftime("%Y-%m-%d")

    rows = load_bag_rows(csv_path)
    details = collect_expiring_bags(rows, cur_date, warning_days)
    summary = summarize_by_station(details)
    markdown = render_alert_markdown(cur_date, csv_path, summary, details, warning_days)
    report_path = save_report(markdown, cur_date)

    notify_result = {"sent": False, "reason": "send_notify=false"}
    if send_notify:
        try:
            notify_result = send_webhook(markdown, summary, cur_date)
        except Exception as e:
            notify_result = {"sent": False, "reason": str(e)}
    
    return {
        "date": cur_date,
        "csv_path": csv_path,
        "alerts": summary,
        "total": sum(summary.values()),
        "report_path": report_path.relative_to(PROJECT_ROOT).as_posix(),
        "notify": notify_result,
    }