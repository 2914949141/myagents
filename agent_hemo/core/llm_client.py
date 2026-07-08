from typing import List, Dict

from openai import OpenAI

from agent_hemo.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT
from agent_hemo.tools import BaseTool

TOOLS = BaseTool.get_all_tools()


class HelloAgentsLLM:
    """
    为本书 "Hello Agents" 定制的LLM客户端。
    它用于调用任何兼容OpenAI接口的服务，并默认使用流式响应。
    """

    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """
        初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载。
        """
        self.model = model or LLM_MODEL
        apiKey = apiKey or LLM_API_KEY
        baseUrl = baseUrl or LLM_BASE_URL
        timeout = timeout or LLM_TIMEOUT

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout)

    def invoke(self, messages: List[Dict[str, str]], temperature: float = 0, tools: List[Dict] = TOOLS) -> object:
        """
        调用大语言模型进行思考，并返回其响应。
        如果使用了流式响应且有工具调用，需要特殊处理。
        
        Args:
            messages: 对话消息列表
            temperature: 温度参数
            tools: 工具定义列表（可选）
        """
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
                # 收集usage信息
                "stream_options": {
                    "include_usage": True
                }
            }
            
            # 如果提供了工具，添加到请求中
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**request_params)

            # 处理流式响应
            collected_content = []
            tool_calls = []
            usage = None
            
            for chunk in response:
                if not chunk.choices:
                    # 最后一个chunk可能只有usage，没有choices
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage = chunk.usage
                    continue
                    
                delta = chunk.choices[0].delta
                
                # 收集文本内容
                content = delta.content or ""
                if content:
                    # print(content, end="", flush=True)
                    collected_content.append(content)
                
                # 收集工具调用信息
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        index = tool_call_delta.index
                        
                        # 初始化新的工具调用
                        if len(tool_calls) <= index:
                            tool_calls.append({
                                "id": "",
                                "name": "",
                                "arguments": ""
                            })
                        
                        # 更新工具调用ID
                        if tool_call_delta.id:
                            tool_calls[index]["id"] = tool_call_delta.id
                        
                        # 更新工具函数名称
                        if tool_call_delta.function and tool_call_delta.function.name:
                            tool_calls[index]["name"] = tool_call_delta.function.name
                        
                        # 累积工具参数
                        if tool_call_delta.function and tool_call_delta.function.arguments:
                            tool_calls[index]["arguments"] += tool_call_delta.function.arguments
                
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage

            print("✅ 大语言模型响应成功！")
            print()  # 在流式输出结束后换行

            # 创建一个简单的消息对象
            class SimpleMessage:
                def __init__(self, content_text, tool_calls_list=None, usage=None):
                    self.content = [{"type": "text", "text": content_text}] if content_text else []
                    self.tool_calls = []
                    self.usage = usage
                    # 转换工具调用格式
                    if tool_calls_list:
                        for tc in tool_calls_list:
                            class ToolCall:
                                def __init__(self, tc_id, tc_name, tc_args):
                                    self.id = tc_id
                                    self.function = type('Function', (), {
                                        'name': tc_name,
                                        'arguments': tc_args
                                    })()
                            
                            self.tool_calls.append(ToolCall(
                                tc["id"],
                                tc["name"],
                                tc["arguments"]
                            ))

            
            return self._build_simple_message("".join(collected_content), tool_calls if tool_calls else None, usage=usage)

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None

    def invoke_stream(self, messages, temperature=0, tools=TOOLS):
        """
        流式调用 LLM。
        先 yield ('token', 文本片段)
        最后 yield ('done', SimpleMessage对象)  —— 和 invoke() 返回的一样
        """
        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {
                "include_usage": True
            },
        }
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**request_params)

        collected_content = []
        tool_calls = []
        usage = None

        for chunk in response:
            if not chunk.choices:
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage
                continue
            
            delta = chunk.choices[0].delta
            content = delta.content or ""
            if content:
                collected_content.append(content)
                yield ('token', content)
            
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    index = tool_call_delta.index
                    if len(tool_calls) <= index:
                        tool_calls.append({"id": "", "name": "", "arguments": ""})
                    if tool_call_delta.id:
                        tool_calls[index]["id"] = tool_call_delta.id
                    if tool_call_delta.function and tool_call_delta.function.name:
                        tool_calls[index]["name"] = tool_call_delta.function.name
                    if tool_call_delta.function and tool_call_delta.function.arguments:
                        tool_calls[index]["arguments"] += tool_call_delta.function.arguments

            if hasattr(chunk, "usage") and chunk.usage:
                usage = chunk.usage
    
        message = self._build_simple_message("".join(collected_content), tool_calls if tool_calls else None, usage=usage)
        yield("done", message)


    def _build_simple_message(self, content_text, tool_calls_list=None, usage=None):
        class SimpleMessage:
            def __init__(self, content_text, tool_calls_list=None, usage=None):
                self.content = [{"type": "text", "text": content_text}] if content_text else []
                self.tool_calls = []
                self.usage = usage
                if tool_calls_list:
                    for tc in tool_calls_list:
                        class ToolCall:
                            def __init__(self, tc_id, tc_name, tc_args):
                                self.id = tc_id
                                self.function = type('Function', (), {
                                    'name': tc_name,
                                    'arguments': tc_args
                                })()
                        self.tool_calls.append(ToolCall(tc["id"], tc["name"], tc["arguments"]))
        return SimpleMessage(content_text, tool_calls_list, usage)

# --- 客户端使用示例 ---
# if __name__ == '__main__':
    # try:
    #     llmClient = HelloAgentsLLM()
    #
    #     exampleMessages = [
    #         {"role": "system", "content": "You are a helpful assistant that writes Python code."},
    #         {"role": "user", "content": "写一个快速排序算法"}
    #     ]
    #
    #     print("--- 调用LLM ---")
    #     responseText = llmClient.think(exampleMessages)
    #     if responseText:
    #         print("\n\n--- 完整模型响应 ---")
    #         print(responseText)
    #
    # except ValueError as e:
    #     print(e)
