import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url=os.environ["ANTHROPIC_BASE_URL"],
)

history = []

while True:
    user_input = input("你: ")

    history.append({"role": "user", "content": user_input})

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=history
    )

    reply = next(b.text for b in message.content if b.type == "text")
    print(f"[Agent回答]: {reply}\n")
    history.append({"role": "assistant", "content": reply})
