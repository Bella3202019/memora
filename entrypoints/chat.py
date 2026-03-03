"""
CLI chat interface for querying your memory knowledge graph.

Usage:
    python3 -m entrypoints.chat
"""
import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src.agents.chat_agent import SYSTEM_PROMPT, chat

load_dotenv()
logging.basicConfig(level=logging.WARNING)

CHAT_DIR = Path(__file__).parent.parent / "data" / "chat"


def get_chat_file() -> Path:
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_DIR / f"{date.today()}.json"


def load_history() -> list[dict]:
    path = get_chat_file()
    if path.exists():
        return json.loads(path.read_text())
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def save_history(messages: list[dict]) -> None:
    get_chat_file().write_text(json.dumps(messages, indent=2, ensure_ascii=False))


async def main() -> None:
    print("Hey, feel free to chat with another echo of yourself.")
    print("Type 'quit' or press Ctrl+C to exit.\n")

    messages = load_history()

    # Show how many prior messages exist in today's session
    prior = len([m for m in messages if m["role"] == "user"])
    if prior:
        print(f"(Resuming today's session — {prior} previous messages)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            response = await chat(messages)
            print(f"\nAssistant: {response}\n")
            save_history(messages)
        except Exception as e:
            print(f"\n[Error] {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
