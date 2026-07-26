"""Conversation source: ChatGPT/Claude export JSON and plain-text transcripts.

Two-party dialogues. Format is auto-detected per file:
  - JSON list with "mapping"        -> ChatGPT export
  - JSON list with "chat_messages"  -> Claude export
  - anything else (.txt/.md)        -> speaker-labeled plain-text transcript
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Tuple

from src.sources.base import Source, SourceDocument

logger = logging.getLogger(__name__)

SPEAKER_LINE = re.compile(r"^(\w[\w .-]*):\s*(.*)$")
USER_LABELS = {"user", "human", "me"}


def _fmt(turns: List[Tuple[str, str]]) -> str:
    lines = []
    for role, text in turns:
        label = "[User]" if role.lower() in USER_LABELS else "[Assistant]"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _iso(ts: str) -> str:
    return ts.replace("Z", "")[:19]


def _parse_chatgpt(conv: dict) -> Tuple[str, str]:
    turns = []
    for node in conv.get("mapping", {}).values():
        msg = node.get("message")
        if not msg:
            continue
        parts = (msg.get("content") or {}).get("parts") or []
        text = " ".join(p for p in parts if isinstance(p, str)).strip()
        if text:
            turns.append((msg["author"]["role"], text))
    ts = datetime.fromtimestamp(
        conv.get("create_time", 0), tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%S")
    return _fmt(turns), ts


def _parse_claude(conv: dict) -> Tuple[str, str]:
    turns = [
        (m.get("sender", ""), m.get("text", ""))
        for m in conv.get("chat_messages", [])
        if m.get("text")
    ]
    return _fmt(turns), _iso(conv.get("created_at", ""))


def _parse_plaintext(raw: str) -> str:
    turns = []
    for line in raw.splitlines():
        m = SPEAKER_LINE.match(line.strip())
        if m:
            turns.append((m.group(1), m.group(2)))
    return _fmt(turns) if turns else raw


class ConversationSource(Source):
    prompt_preamble = (
        "This is a two-party conversation (the user talking with an "
        "assistant or another person). Extract ONLY the USER's memories: "
        "their experiences, their emotions, their self-knowledge. Never "
        "extract the assistant's or other speaker's statements as the "
        "user's memories. Advice the user received is not an experience; "
        "the user ACTING on or REACTING to it can be."
    )

    def discover(self) -> Iterator[SourceDocument]:
        for root in self.config.paths:
            files = sorted(
                {f for pat in self.config.include for f in Path(root).glob(pat)}
            )
            for f in files:
                if not f.is_file():
                    continue
                yield from self._parse_file(f)

    def _parse_file(self, f: Path) -> Iterator[SourceDocument]:
        raw = f.read_text(encoding="utf-8", errors="replace")
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        if f.suffix == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Skipping unparseable JSON: {f}")
                return
            if not isinstance(data, list):
                data = [data]
            for i, conv in enumerate(data):
                if "mapping" in conv:
                    text, ts = _parse_chatgpt(conv)
                elif "chat_messages" in conv:
                    text, ts = _parse_claude(conv)
                else:
                    logger.warning(f"Skipping unrecognized conversation in {f}")
                    continue
                if not text:
                    continue
                yield SourceDocument(
                    doc_id=f"{f.resolve()}#{i}",
                    text=text,
                    timestamp=ts or mtime,
                    source_type="conversation",
                    metadata={"path": str(f), "index": i,
                              "timestamp_source": "native" if ts else "mtime"},
                )
        else:
            text = _parse_plaintext(raw).strip()
            if text:
                yield SourceDocument(
                    doc_id=str(f.resolve()),
                    text=text,
                    timestamp=mtime,
                    source_type="conversation",
                    metadata={"path": str(f), "timestamp_source": "mtime"},
                )
