from myagents.core.llm_client import HelloAgentsLLM
from myagents.memory.memory_store import MemoryStore
from myagents.tools.base_tool import BaseTool, execute_basic_tool
from myagents.utils.logger import AgentTracer
from myagents.utils.token_utils import TokenTracker
from myagents.config import MAX_TURNS, MAX_RETRIES, COMPACT_EVERY
from myagents.tools.dispatch_subagent_tool import _execute_tools_parallel
from typing import List, Dict
import time


class AgentRunner:
    def __init__(self, llm_client: HelloAgentsLLM, agent_name: str = "main"):
        self.llm_client = llm_client
        self.memory_store = MemoryStore()
        self.agent_name = agent_name

    def run(self, history: List[Dict[str, str]], tools=None, max_turns: int = MAX_TURNS) -> str:
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
                return reply
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
                tool_results = _execute_tools_parallel(message.tool_calls)
                history.extend(tool_results)
            step += 1

        tracer.on_run_end(final_result, step, token_tracker.snapshot())
        return final_result

    # relecxion （失败反思重试）
    def run_with_relexion(self, history, tools=None, max_turns: int = MAX_TURNS, max_retries: int = MAX_RETRIES):
        for attempt in range(max_retries + 1):
            result = self.run(history, tools, max_turns)

            if not self._look_like_failure(result):
                return result
            
            # 失败了 注入反思
            history.append({
                "role": "user",
                "content": (f"第{attempt+1}次尝试失败，结果是：{result}\n"
                "请分析失败原因，换一种方式重试"
                ),
            })
            print(f"🔄 Reflexion 重试 ({attempt + 1}/{max_retries})")
        return result

    def _look_like_failure(self, result: str) -> bool:
        failure_keywords = ["错误", "失败", "找不到", "没有找到", "不存在", "超时", "无结果", "⚠️", "Error", "error"]
        return any(kw in result for kw in failure_keywords)

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