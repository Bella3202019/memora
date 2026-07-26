"""Native Google Gemini backend (requires `pip install google-genai`)."""

from __future__ import annotations

import asyncio

from src.llm.base import LLMBackend, extract_json_block


class GeminiBackend(LLMBackend):
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    async def complete_json(self, system: str, user: str) -> dict:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError(
                "google-genai SDK not installed: pip install google-genai"
            )
        client = genai.Client()  # reads GEMINI_API_KEY
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
            ),
        )
        return extract_json_block(response.text)
