import re

_SOURCE_RE = re.compile(r"^\[(\d+)\] 来源: (.+)$", re.MULTILINE)

def extract_source_from_rag_output(tool_output: str) -> list[str]:
    """从 rag_search 工具返回文本里提取 title 列表， 去重保序"""
    if not tool_output or "来源:" not in tool_output:
        return []
    seen = set()
    sources = []
    for _, title in _SOURCE_RE.findall(tool_output):
        title = title.strip()
        if title and title not in seen:
            seen.add(title)
            sources.append(title)
    return sources