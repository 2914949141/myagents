# tools/blood_report_tool.py
import csv
import json
from collections import Counter
from datetime import datetime

from agent_hemo.tools.base_tool import BaseTool
from agent_hemo.utils.sandbox import is_path_allowed
from agent_hemo.settings import PROJECT_ROOT, UTC8, resolve_project_path


class BloodReportTool(BaseTool):
    name = "generate_blood_report"
    description = (
        "生成采血/献浆日报或周报。"
        "用户提到「日报」「周报」「采血统计」「生成报告」时优先调用。"
        "直接传入 csv_path，不要用 run_command 找文件。"
    )

    @classmethod
    def get_parameters(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "csv_path": {
                    "type": "string",
                    "description": "CSV 文件路径, 相对项目根目录，如 data/daily_collection_2025-06-18.csv"
                },
                "report_type": {
                    "type": "string",
                    "enum": ["daily", "weekly"],
                    "description": "报告类型: daily (日报) 或 weekly (周报)",
                },
                "title": {
                    "type": "string",
                    "description": "报告标题，如 '中心血站2025-06-18 采血日报'"
                }
            },
            "required": ["csv_path", "report_type"]
        }

    def execute(self, tool_call) -> str:
        args = json.loads(tool_call.function.arguments)
        csv_path = args["csv_path"]
        report_type = args.get("report_type", "daily")
        title = args.get("title", "采供血日报")

        if not is_path_allowed(csv_path):
            return f"安全限制：路径 '{csv_path}' 不在工作区内"
        
        path = resolve_project_path(csv_path)
        if not path.exists():
            return f"文件不存在: {csv_path}"

        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return "CSV为空或格式不正确"

        stats = self._aggregate(rows)
        md = self._render_markdown(title, report_type, stats, rows)

        out_dir = PROJECT_ROOT / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        date_str = rows[0].get("date", datetime.now(UTC8).strftime("%Y-%m-%d"))
        suffix = "daily" if report_type == "daily" else "weekly"
        out_path = out_dir / f"{date_str}-{suffix}.md"
        out_path.write_text(md, encoding="utf-8")

        return (
            f"报告已生成: {out_path.relative_to(PROJECT_ROOT)}\n"
            f"汇总：总人次 {stats['total_donors']},"
            f"合格 {stats['total_qualified']}, "
            f"淘汰率 {stats['reject_rate']:.1%}, "
            f"采集量 {stats['total_volume_ml']} ml\n"
            f"淘汰原因 Top3: {stats['top_rejections']}"
        )

    def _aggregate(self, rows: list[dict]) -> dict:
        total_donors = sum(int(row["donor_count"]) for row in rows)
        total_qualified = sum(int(r.get("qualified_count") or 0) for r in rows)
        total_volume = sum(int(r.get("volume_ml") or 0) for r in rows)
        rejections = Counter()
        for r in rows:
            reason = (r.get("reject_reason") or "").strip()
            cnt = int(r.get("rejection_count") or 0)
            if reason and cnt:
                rejections[reason] += cnt
        rejected = total_donors - total_qualified
        return {
            "total_donors": total_donors,
            "total_qualified": total_qualified,
            "total_volume_ml": total_volume,
            "reject_rate": rejected / total_donors if total_donors else 0,
            "top_rejections": rejections.most_common(3),
            "by_site": self._group_by(rows, "site"),
            "by_type": self._group_by(rows, "type"),
        }

    def _group_by(self, rows: list[dict], key: str) -> dict:
        """按 site 或 type 分组统计， 累计 donor_count, qualified_count, volume_ml"""
        groups = {}

        for row in rows:
            # groupby的key
            name = row.get(key, "未知").strip()
            if not name or name == "未知":
                continue

            # 第一次遇到这个组，先建一个空壳
            if name not in groups:
                groups[name] = {
                    "donor_count": 0,
                    "qualified_count": 0,
                    "volume_ml": 0,
                }
            
            # 累加统计数据
            groups[name]["donor_count"] += int(row.get("donor_count") or 0)
            groups[name]["qualified_count"] += int(row.get("qualified_count") or 0)
            groups[name]["volume_ml"] += int(row.get("volume_ml") or 0)
    
        return groups

    def _rate(self, donors: int, qualified: int):
        if donors == 0:
            return "0.0%"
        return f"{(donors - qualified) / donors:.1%}"

    def _render_markdown(self, title: str, report_type: str, stats: dict, rows: list[dict]) -> str:
        """渲染 Markdown 报告"""
        date_str = rows[0].get("date", "未知日期") if rows else "未知日期"
        type_label = "日报" if report_type == "daily" else "周报"

        lines = [
            f"# {title}",
            "",
            f"> 报告类型：{type_label} | 日期：{date_str}",
            "",
            "## 总体概况",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总人次 | {stats['total_donors']} |",
            f"| 合格人次 | {stats['total_qualified']} |",
            f"| 淘汰率 | {stats['reject_rate']:.1%} |",
            f"| 采集量 | {stats['total_volume_ml']} ml |",
            "",
            "## 各站点统计",
            "",
            "| 站点 | 人次 | 合格 | 淘汰率 | 采集量(ml) |",
            "|------|------|------|--------|------------|",
        ]
    
        # 遍历by_site字典
        for site, data in stats['by_site'].items():
            donors = data['donor_count']
            qualified = data['qualified_count']
            volume = data['volume_ml']
            lines.append(f"| {site} | {donors} | {qualified} | {self._rate(donors, qualified)} | {volume} |")

        lines += [
                "",
                "## 各类型统计",
                "",
                "| 类型 | 人次 | 合格 | 淘汰率 | 采集量(ml) |",
                "|------|------|------|--------|------------|",
            ]

            
        # 遍历by_type字典
        for blood_type, data in stats['by_type'].items():
            donors = data['donor_count']
            qualified = data['qualified_count']
            volume = data['volume_ml']
            lines.append(f"| {blood_type} | {donors} | {qualified} | {self._rate(donors, qualified)} | {volume} |")


        lines += ["", "## 淘汰原因 Top3", ""]   

        if stats['top_rejections']:
            for i, (reason, count) in enumerate(stats['top_rejections'], 1):
                lines.append(f"{i}. {reason} - {count} 人")
        else:
            lines.append("暂无淘汰记录")

        return "\n".join(lines)