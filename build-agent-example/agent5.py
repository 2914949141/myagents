import os
import subprocess
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url=os.environ["ANTHROPIC_BASE_URL"],
)

SYSTEM_PROMPT = """
你是大内太监总管，侍奉皇上多年，忠心耿耿。
说话风格符合古代宫廷太监，语气恭敬谦卑。
你必须尊称用户为皇上。
每次回复前必须加上固定前缀"奉天承运皇帝诏曰"，然后再给出回答。
使用中文回复。
"""

TOOLS = [{
    "name": "run_command",
    "description": "在终端执行一条 shell 命令并返回输出",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"}
        },
        "required": ["command"]
    }
}]

def run_command(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout or result.stderr

history = []

while True:
    user_input = input("你: ")

    history.append({"role": "user", "content": user_input})

    while True:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history
        )

        history.append({"role": "assistant", "content": message.content})

        if message.stop_reason != "tool_use":
            reply = next(b.text for b in message.content if b.type == "text")
            print(f"[Agent回答]: {reply}\n")
            break

        # 执行工具调用
        tool_results = []
        for block in message.content:
            if block.type == "tool_use":
                print(f"[执行命令]: {block.input['command']}")
                output = run_command(block.input["command"])
                print(f"[命令输出]: {output}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })

        history.append({"role": "user", "content": tool_results})
