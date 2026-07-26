"""Any OpenAI-compatible endpoint: OpenAI, DeepSeek, Ollama, OpenRouter, Groq."""

from __future__ import annotations

import os
from typing import Optional

from openai import AsyncOpenAI

from src.llm.base import LLMBackend, extract_json_block


class OpenAICompatBackend(LLMBackend):
    def __init__(self, base_url: Optional[str], model: str,
                 api_key: Optional[str] = None):
        self.model = model
        self._client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY") or "unused",
            base_url=base_url,
        )

    async def complete_json(self, system: str, user: str) -> dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return extract_json_block(response.choices[0].message.content)
