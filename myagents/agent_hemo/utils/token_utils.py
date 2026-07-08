def parse_usage(usage) -> dict:
    """把 API 返回的 usage 对象转成普通 dict"""
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # openAI SDK对象
    if hasattr(usage, "prompt_tokens"):
         return {
        "prompt_tokens": usage.prompt_tokens or 0,
        "completion_tokens": usage.completion_tokens or 0,
        "total_tokens": usage.total_tokens or 0,
    }

    # 已经是dict
    if isinstance(usage, dict):
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

class TokenTracker:

    """跨多次LLM调用累计Token使用情况"""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.call_count = 0

    def add(self, usage) -> dict:
        """记录一次调用返回本次token数"""
        parsed = parse_usage(usage)
        self.prompt_tokens += parsed["prompt_tokens"]
        self.completion_tokens += parsed["completion_tokens"]
        self.total_tokens += parsed["total_tokens"]
        self.call_count += 1
        return parsed

    def snapshot(self) -> dict:
        """返回当前累计值"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "call_count": self.call_count,
        }