"""Claude subscription backend: shells out to `claude -p` (Claude Code CLI).

Zero marginal cost on a Claude subscription. Requirements:
  - `claude` CLI installed and logged in
  - ANTHROPIC_API_KEY must NOT be set (the CLI would silently bill the API)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Optional

from src.llm.base import LLMBackend, extract_json_block

logger = logging.getLogger(__name__)


class ClaudeCLIBackend(LLMBackend):
    def __init__(self, model: Optional[str] = None):
        self.model = model  # None = CLI default

    async def complete_json(self, system: str, user: str) -> dict:
        if shutil.which("claude") is None:
            raise RuntimeError(
                "`claude` CLI not found. Install Claude Code and log in, "
                "or switch llm.backend in ~/.memora/config.yaml."
            )
        if os.getenv("ANTHROPIC_API_KEY"):
            logger.warning(
                "ANTHROPIC_API_KEY is set — `claude -p` will bill the API "
                "instead of your subscription. Unset it to use plan credit."
            )
        prompt = (
            f"{system}\n\n---\n\n{user}\n\n"
            "Respond with ONLY the JSON object, no other text."
        )
        cmd = ["claude", "-p", "--output-format", "json"]
        if self.model:
            cmd += ["--model", self.model]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(prompt.encode("utf-8"))
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p failed: {stderr.decode()[:500]}")
        envelope = json.loads(stdout.decode("utf-8"))
        # `claude -p --output-format json` wraps the reply in {"result": "..."}
        return extract_json_block(envelope["result"])
