import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url=os.environ["ANTHROPIC_BASE_URL"],
)
MODEL = os.environ["ANTHROPIC_MODEL"]

while True:
    user_input = input("你: ")

    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": user_input}]
    )

    for block in message.content:
        if block.type == "text":
            print(f"[Agent回答]: {block.text}\n")
