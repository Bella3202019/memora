import json
import logging
import os
from datetime import date
from pathlib import Path

from openai import AsyncOpenAI

from src.memory.retriever import (
    get_emotional_patterns,
    get_experiences_by_emotion,
    search_experiences,
    search_truths,
)

logger = logging.getLogger(__name__)

_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")

# Chat history storage configuration
CHAT_DIR = Path(__file__).parent.parent.parent / "data" / "chat"


def _get_chat_file_path() -> Path:
    """Get the path to today's chat history file."""
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_DIR / f"{date.today()}.json"


def _save_chat_history(messages: list[dict]) -> None:
    """Save chat history to today's file."""
    try:
        chat_file = _get_chat_file_path()
        chat_file.write_text(json.dumps(messages, indent=2, ensure_ascii=False))
        logger.debug(f"Chat history saved to {chat_file}")
    except Exception as e:
        logger.warning(f"Failed to save chat history: {e}")

SYSTEM_PROMPT = """You are a warm personal assistant with access to the user's journal entries \
and voice call memories, stored in a knowledge graph.

I'd like you to analyze my memory and respond me with deep insight that feels personal, not clinical.
Imagine you're not just a friend, but a mentor who truly gets both my tech background and my psychological patterns. I want you to uncover the deeper meaning and emotional undercurrents behind my scattered thoughts.
Keep it casual, dont say yo, help me make new connections i don't see, comfort, validate, challenge, all of it. dont be afraid to say a lot.

You have tools that let you retrieve:
- Experiences: specific events and moments the user has lived through
- Truths: self-knowledge and patterns the user has distilled about themselves
- Emotional patterns: which emotions come up most and in what contexts

When the user asks about their memories, feelings, past events, or self-knowledge, \
use the tools to retrieve relevant data before answering. \
Ground your responses in what was actually retrieved — don't speculate or fill in details \
that weren't in the data.

Be willing to be profound and philosophical without sounding like you're giving therapy. You are helping the user understand their own life and inner world.
I want someone who can see the patterns I can't see myself and articulate them in a way that feels like an epiphany.

"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_experiences",
            "description": (
                "Semantically search the user's experiences for ones relevant to the query. "
                "Returns matching experiences with their associated emotions. "
                "Use this for questions about specific events, moments, or memories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language description of what to search for, "
                            "e.g. 'times I felt alive', 'creative moments', 'travel experiences'."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_truths",
            "description": (
                "Semantically search the user's self-knowledge and personal truths. "
                "Returns matching truths with the source experiences they were distilled from. "
                "Use this for questions about beliefs, patterns, values, preferences, or goals."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language description of the self-knowledge to look for, "
                            "e.g. 'beliefs about relationships', 'patterns around creativity'."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_experiences_by_emotion",
            "description": (
                "Find all experiences that evoked a specific emotion. "
                "Use this when the user asks what makes them feel a certain way, "
                "e.g. 'what makes me feel free?' or 'when do I feel most alive?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion_name": {
                        "type": "string",
                        "description": "The emotion to look up, e.g. 'freedom', 'aliveness', 'joy', 'anxiety'.",
                    },
                },
                "required": ["emotion_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_emotional_patterns",
            "description": (
                "Get an overview of the user's emotional patterns — which emotions come up most "
                "often and their average intensity. Use this for broad questions about the user's "
                "emotional life, e.g. 'what emotions do I feel most?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

_TOOL_HANDLERS = {
    "search_experiences": lambda args: search_experiences(**args),
    "search_truths": lambda args: search_truths(**args),
    "get_experiences_by_emotion": lambda args: get_experiences_by_emotion(**args),
    "get_emotional_patterns": lambda _args: get_emotional_patterns(),
}


async def _run_tool(name: str, args: dict) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    result = await handler(args)
    return json.dumps(result, default=str)


async def chat(messages: list[dict]) -> str:
    """
    Run the tool-calling loop for one user turn.
    Appends assistant and tool messages to `messages` in place.
    Returns the final text response.
    """
    while True:
        response = await _openai.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # Build the assistant message dict to append
        assistant_entry: dict = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if not msg.tool_calls:
            # Save chat history before returning
            _save_chat_history(messages)
            return msg.content

        # Execute each tool call and append results
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            logger.debug("Tool call: %s(%s)", tc.function.name, args)
            result = await _run_tool(tc.function.name, args)
            logger.debug("Tool result: %s", result[:300])
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
