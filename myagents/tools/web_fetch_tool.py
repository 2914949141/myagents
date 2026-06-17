from myagents.tools.base_tool import BaseTool
import urllib.request
from html.parser import HTMLParser
import re


class WebFetchTool(BaseTool):
    """web工具 - 获取指定 URL 的网页内容，支持文本提取模式"""

    name = "web_fetch"
    description = "获取指定 URL 的网页内容，支持文本提取模式"

    @classmethod
    def get_parameters(cls) -> dict:
        """返回参数定义"""
        return {
                "type": "object",
                "properties": {
                    "url":          {"type": "string",  "description": "要访问的完整 URL"},
                    "extract_mode": {"type": "string",  "description": "提取模式：text（纯文本，默认）或 raw（原始 HTML）"},
                    "max_chars":    {"type": "integer", "description": "最大返回字符数，默认 8000"}
                },
                "required": ["url"]
        }

    def execute(self, tool_call) -> str:
        import json
        args = json.loads(tool_call.function.arguments)
        url = args['url']
        extract_mode = args.get('extract_mode', 'text')
        max_chars = args.get('max_chars', 8000)

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            return f"Error fetching {url}: {e}"

        if extract_mode == "text":
            parser = _TextExtractor()
            parser.feed(raw)
            text = parser.get_text()
        else:
            text = raw

        return text[:max_chars]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts)).strip()