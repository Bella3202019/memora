"""LLM backend interface: one job — structured JSON completion."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class LLMBackend(ABC):
    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict:
        """Send prompts, return the parsed JSON object from the response."""


def extract_json_block(text: str) -> dict:
    """Parse a JSON object out of raw model text (fences/prose tolerated)."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
