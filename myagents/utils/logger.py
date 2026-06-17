import json
import logging
import time
import uuid
from datetime import datetime

from myagents.config import LOGS_DIR, UTC8

LOGS_DIR.mkdir(exist_ok=True)

def setup_logger(name: str = "myagent") -> logging.Logger:
    """配置同时输出到控制台和文件的 logger"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)

    # 控制台： 人类可读
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    
    # 文件：JSON行， 方便解析
    file_handler = logging.FileHandler(
        LOGS_DIR / f"{datetime.now(UTC8).strftime('%Y-%m-%d')}.jsonl",
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    # logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()

class AgentTracer:
    """追踪一次Agent运行的所有步骤"""

    def __init__(self, agent_name: str = "main") -> None:
        self.trace_id = str(uuid.uuid4())[:8]
        self.agent_name = agent_name
        self.start_time = time.time()
        self.step_count = 0

    def _log(self, event: str, **data):
        record = {
            "time": datetime.now(UTC8).isoformat(timespec="seconds"),
            "trace_id": self.trace_id,
            "agent": self.agent_name,
            "event": event,
            **data,
        }
        logger.info(json.dumps(record, ensure_ascii=False))

    def on_run_start(self, user_input: str):
        self._log("run_start", user_input=user_input[:200])

    def on_llm_start(self, step: int, message_count: int):
        self.step_count = step
        self._log("llm_start", step=step, message_count=message_count)

    def on_llm_end(self, step: int, has_tool_calls: bool, latency_ms: float,
            prompt_tokens: int=0, completion_tokens: int=0, total_tokens: int=0):
        self._log("llm_end", step=step, 
                has_tool_calls=has_tool_calls, 
                latency_ms=round(latency_ms, 1),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens)

    def on_tool_start(self, tool_name: str, arguments: str):
        self._log("tool_start", step=self.step_count, 
                    tool_name=tool_name, arguments=arguments[:300])

    def on_tool_end(self, tool_name: str, output: str, latency_ms: float):
        is_error = output.startswith("错误") or output.startswith("工具执行失败")
        self._log("tool_end", step=self.step_count, 
                tool=tool_name,
                output_len=len(output),
                latency_ms=round(latency_ms, 1),
                is_error=is_error)

    def on_run_end(self, reply: str, total_steps: int, token_summary: dict=None):
        elapsed = round((time.time() - self.start_time) * 1000, 1)
        data = {
            "total_steps": total_steps,
            "reply_len": len(reply),
            "total_latency_ms": elapsed,
        }
        if token_summary:
            data.update(token_summary)  # prompt_tokens, completion_tokens, total_tokens, llm_call_count
        self._log("run_end", **data)


    def on_compact(self, before_count: int, after_count: int):
        self._log("compact", 
        message_before=before_count, 
        message_after=after_count)
    
    def on_security_block(self, tool_name: str, reason: str):
        self._log("security_block", tool=tool_name, reason=reason)