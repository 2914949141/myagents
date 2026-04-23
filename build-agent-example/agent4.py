import os
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

history = []

while True:
    user_input = input("你: ")

    history.append({"role": "user", "content": user_input})

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=history
    )

    reply = next(b.text for b in message.content if b.type == "text")
    print(f"[Agent回答]: {reply}\n")
    history.append({"role": "assistant", "content": reply})
