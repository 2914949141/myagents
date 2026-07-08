from agent_hemo.core.llm_client import HelloAgentsLLM
from agent_hemo.memory.memory_store import MemoryStore
from agent_hemo.tools.base_tool import BaseTool, execute_basic_tool
from agent_hemo.utils.logger import AgentTracer
from agent_hemo.utils.token_utils import TokenTracker
from agent_hemo.settings import MAX_TURNS, MAX_RETRIES, COMPACT_EVERY
from agent_hemo.tools.dispatch_subagent_tool import _execute_tools_parallel
from typing import List, Dict, Iterator
import time

from agent_hemo.utils.logger import reset_current_tracer, set_current_tracer
from agent_hemo.utils.rag_sources import extract_source_from_rag_output


class AgentRunner:
    def __init__(self, llm_client: HelloAgentsLLM, agent_name: str = "main"):
        self.llm_client = llm_client
        self.memory_store = MemoryStore()
        self.agent_name = agent_name

    def run(self, history: List[Dict[str, str]], tools=None, max_turns: int = MAX_TURNS, quiet: bool = False) -> tuple[str, list[str]]:
        sources: list[str] = []
        self._last_run_had_tool_error = False
        tracer = AgentTracer(agent_name=self.agent_name)
        token_tracker = TokenTracker()

        # 从history里取最后一条用户信息
        for msg in reversed(history):
            if msg.get("role") == "user":
                user_input = msg.get("content", "")
                break
        tracer.on_run_start(user_input)
        step = 1
        final_result = "无结果"
        token = set_current_tracer(tracer)
        try:
            while step <= max_turns:
                # 记录LLM调用开始
                t0 = time.time()
                tracer.on_llm_start(step, len(history))
                if tools is not None:
                    message = self.llm_client.invoke(messages=history, tools=tools)
                else:
                    message = self.llm_client.invoke(messages=history)
                
                latency = (time.time() - t0) * 1000

                # 解析并积累token
                usage = getattr(message, "usage", None)
                step_tokens = token_tracker.add(usage)

                if not message:
                    tracer.on_llm_end(step, False, latency)
                    final_result = "LLM调用失败"
                    break
                has_tool_calls = bool(hasattr(message, "tool_calls") and message.tool_calls)
                tracer.on_llm_end(step, 
                    has_tool_calls, 
                    latency,
                    prompt_tokens=step_tokens["prompt_tokens"],
                    completion_tokens=step_tokens["completion_tokens"],
                    total_tokens=step_tokens["total_tokens"],
                )
                # 没有调用工具直接返回文本
                if not has_tool_calls:
                    reply = self._extract_reply(message)
                    if not quiet:
                        print(f"\n[Agent回答]: {reply}\n")
                    history.append({"role": "assistant", "content": reply})
                    # 记录对话到 memory
                    self.memory_store.append_history("assistant", reply)

                    # 如果对话轮数较多，可以考虑归档（简化版：每5轮归档一次）
                    assistant_count = sum(1 for h in history if h.get("role") == "assistant")
                    if assistant_count % COMPACT_EVERY == 0:
                        before = len(history)
                        history[:] = self.memory_store.summarize_and_compact(history)
                        tracer.on_compact(before, len(history))
                    tracer.on_run_end(reply, step, token_tracker.snapshot())
                    return reply, sources
                else:
                    # 将 tool_calls 转换为可序列化的字典格式
                    tool_calls_dict = []
                    for tc in message.tool_calls:
                        tool_calls_dict.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        })

                    assistant_message = {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": tool_calls_dict  # 使用转换后的字典列表
                    }
                    history.append(assistant_message)
                    # 执行工具调用
                    tool_results = _execute_tools_parallel(message.tool_calls, tracer=tracer)
                    for tc, tr in zip(message.tool_calls, tool_results):
                        if tc.function.name == "rag_search":
                            for s in extract_source_from_rag_output(tr.get("content", "")):
                                if s not in sources:
                                    sources.append(s)
                    for tr in tool_results:
                        content = tr.get("content", "")
                        if content.startswith("错误") or content.startswith("工具执行失败"):
                            self._last_run_had_tool_error = True
                    history.extend(tool_results)
                step += 1
        finally:
            reset_current_tracer(token)
        tracer.on_run_end(final_result, step, token_tracker.snapshot())
        return final_result, sources

    # relecxion （失败反思重试）
    def run_with_relexion(self, history, tools=None, max_turns: int = MAX_TURNS, max_retries: int = MAX_RETRIES, quiet: bool = False):
        all_sources: list[str] = []
        for attempt in range(max_retries + 1):
            result, sources = self.run(history, tools, max_turns, quiet=quiet)
            for s in sources:
                if s not in all_sources:
                    all_sources.append(s)

            if not self._look_like_failure(result):
                return result, all_sources
            
            # 失败了 注入反思
            history.append({
                "role": "user",
                "content": (f"第{attempt+1}次尝试失败，结果是：{result}\n"
                "请分析失败原因，换一种方式重试"
                ),
            })
            print(f"🔄 Reflexion 重试 ({attempt + 1}/{max_retries})")
        return result, all_sources

    def run_with_stream(self, history: List[Dict[str, str]], tools=None, max_turns: int = MAX_TURNS) -> Iterator[dict]:
        """
        产出SSE 事件字典
        {"type": "status", "content": "..."}
        {"type": "token", "content": "..."}
        {"type": "done", "reply": "...", "sources": ["..."]}
        """
        self._last_run_had_tool_error = False
        sources: list[str] = []
        tracer = AgentTracer(agent_name=self.agent_name)
        token_tracker = TokenTracker()
        step = 1
        token = set_current_tracer(tracer)
        try:
            while step <= max_turns:
                # 记录LLM调用开始
                t0 = time.time()
                tracer.on_llm_start(step, len(history))

                message = None
                if tools is not None:
                    stream  = self.llm_client.invoke_stream(messages=history, tools=tools)
                else:
                    stream = self.llm_client.invoke_stream(messages=history)
                
                for event_type, data in stream:
                    if event_type == "token":
                        yield {"type": "token", "content": data}
                    elif event_type == "done":
                        message = data
                
                latency = (time.time() - t0) * 1000
                usage = getattr(message, "usage", None)
                step_tokens = token_tracker.add(usage)

                if not message:
                    yield {"type": "error", "content": "LLM调用失败"}
                    return 
                has_tool_calls = bool(message.tool_calls)
                tracer.on_llm_end(step, has_tool_calls, latency, prompt_tokens=step_tokens["prompt_tokens"], completion_tokens=step_tokens["completion_tokens"], total_tokens=step_tokens["total_tokens"])

                if not has_tool_calls:
                    reply = self._extract_reply(message)
                    history.append({"role": "assistant", "content": reply})
                    self.memory_store.append_history("assistant", reply)
                    yield {"type": "done", "reply": reply, "sources": sources}
                    tracer.on_run_end(reply, step, token_tracker.snapshot())
                    return
                
                # 有工具调用: 发status 执行工具 继续下一轮
                tool_calls_dict = []
                for tc in message.tool_calls:
                        tool_calls_dict.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        })

                assistant_message = {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": tool_calls_dict  # 使用转换后的字典列表
                }
                history.append(assistant_message)

                for tc in message.tool_calls:
                    yield {"type": "status", "content": f"正在调用 {tc.function.name}"}

                tool_results = _execute_tools_parallel(message.tool_calls, tracer=tracer)
                for tc, tr in zip(message.tool_calls, tool_results):
                    if tc.function.name == "rag_search":
                        for s in extract_source_from_rag_output(tr.get("content", "")):
                            if s not in sources:
                                sources.append(s)
                history.extend(tool_results)
                step += 1

            yield {"type": "done", "reply": "无结果", "sources": sources}
        finally:
            reset_current_tracer(token)

    def _look_like_failure(self, result: str) -> bool:
        # 整轮 run 的硬失败
        if result in ("无结果", "LLM调用失败"):
            return True
        if getattr(self, "_last_run_had_tool_error", False):
            return True
        # 只匹配[开头]或固定失败模板， 避免正文里误伤
        failure_prefixes = (
            "抱歉, 知识库没有找到",
            "错误：",
            "工具执行失败",
            "安全限制：",
        )
        stripped = result.strip()
        if any(stripped.startswith(prefix) for prefix in failure_prefixes):
            return True
        return False

    def _extract_reply(self, message) -> str:
        """从message对象提取文本"""
        if hasattr(message, 'content'):
            if isinstance(message.content, list):
                return "".join(
                    item.get("text", "")
                    for item in message.content
                    if item.get("type") == "text"
                )
            return message.content or ""
        return str(message)