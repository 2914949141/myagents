import json
import re
from types import SimpleNamespace

def make_tool_call(name: str, arguments: dict):
    return SimpleNamespace(
        id="api",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False)
        ),
    )

def parse_report_path(tool_output: str) -> str | None:
    # BloodReportTool 返回：报告已生成: reports/2026-06-25-daily.md\n
    m = re.search(r"报告已生成:\s*(\S+)", tool_output)
    return m.group(1) if m else None