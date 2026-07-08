# tools/check_plasma_expiry_tool.py
import csv
import json
from datetime import date, datetime

from agent_hemo.tools.base_tool import BaseTool
from agent_hemo.settings import resolve_project_path


class CheckPlasmaExpiryTool(BaseTool):
    name = "check_plasma_expiry"
    description = (
        "检查临期血浆信息"
        "适用于检查临期血浆信息，并及时提醒用户处理，及时发布回访计划，避免血浆过期"
    )

    @classmethod
    def get_parameters(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "csv_path": {
                    "type": "string",
                    "description": "获取临期血浆信息文件路径, 相对项目根目录，如 data/bag_info.csv"
                },
                "date": {
                    "type": "string",
                    "description": "日期，如 '2026-06-18'，默认当天"
                }
            },
            "required": ["csv_path", "date"]
        }

    def execute(self, tool_call) -> str:
        args = json.loads(tool_call.function.arguments)
        csv_path = args["csv_path"]
        cur_date = args["date"]

        path = resolve_project_path(csv_path)
        if not path.exists():
            return f"文件不存在: {csv_path}"

        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return "CSV为空或格式不正确"

        expiry_count = self._get_expiry_count(rows, cur_date)
        return f"临期血浆信息: {expiry_count}"

    @staticmethod
    def _parse_date(value: str) -> date:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()

    def _get_expiry_count(self, rows: list[dict], cur_date: str) -> dict:
        """获取各个浆站的临期血浆数, cur_date 格式为 '2026-06-18'"""
        today = self._parse_date(cur_date)
        shelf_life_days = 365
        warning_days = 30
        # 效期 365 天：临期 = 采集后第 (365-30)～365 天，即距失效不足 30 天
        min_age = shelf_life_days - warning_days  # 335
        max_age = shelf_life_days  # 365

        expiry_count = {}
        for row in rows:
            status = (row.get("quality_status") or "").strip()
            if status.startswith("EXP") or status.startswith("QUA"):
                continue
            age_days = (today - self._parse_date(row["collect_time"])).days
            if min_age <= age_days <= max_age:
                station = row["station_name"].strip()
                expiry_count[station] = expiry_count.get(station, 0) + 1
        return expiry_count