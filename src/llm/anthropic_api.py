"""Native Anthropic API backend (requires `pip install anthropic`)."""

from __future__ import annotations

from src.llm.base import LLMBackend, extract_json_block


class AnthropicBackend(LLMBackend):
    def __init__(self, model: str = "claude-sonnet-5"):
        self.model = model

    async def complete_json(self, system: str, user: str) -> dict:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError(
                "anthropic SDK not installed: pip install anthropic"
            )
        client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY
        response = await client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            messages=[{
                "role": "user",
                "content": user + "\n\nRespond with ONLY the JSON object.",
            }],
        )
        return extract_json_block(response.content[0].text)
