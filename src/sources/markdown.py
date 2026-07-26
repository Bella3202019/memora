"""Markdown/text source: .md/.txt files in user-configured directories."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Tuple

from src.sources.base import Source, SourceDocument

DIARY_FILENAME = re.compile(
    r"\[[A-F0-9-]+\]-\[(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\]",
    re.IGNORECASE,
)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
FM_DATE = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?))?\s*$", re.M)


def _strip_frontmatter(text: str) -> Tuple[str, Optional[str]]:
    """Return (body, frontmatter_timestamp_or_None)."""
    m = FRONTMATTER.match(text)
    if not m:
        return text, None
    fm = FM_DATE.search(m.group(1))
    ts = None
    if fm:
        time_part = fm.group(2) or "00:00"
        if len(time_part) == 5:
            time_part += ":00"
        ts = f"{fm.group(1)}T{time_part}"
    return text[m.end():], ts


def _resolve_timestamp(path: Path, fm_ts: Optional[str]) -> Tuple[str, str]:
    """Fallback chain: filename pattern -> frontmatter -> mtime."""
    m = DIARY_FILENAME.match(path.name)
    if m:
        y, mo, d, h, mi, s = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:{s}", "filename"
    if fm_ts:
        return fm_ts, "frontmatter"
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime.strftime("%Y-%m-%dT%H:%M:%S"), "mtime"


class MarkdownSource(Source):
    prompt_preamble = ""  # the certified diary path: core prompt only

    def discover(self) -> Iterator[SourceDocument]:
        for root in self.config.paths:
            root_path = Path(root)
            files = sorted(
                {f for pattern in self.config.include for f in root_path.glob(pattern)}
            )
            for f in files:
                if not f.is_file():
                    continue
                raw = f.read_text(encoding="utf-8", errors="replace").strip()
                body, fm_ts = _strip_frontmatter(raw)
                timestamp, ts_source = _resolve_timestamp(f, fm_ts)
                yield SourceDocument(
                    doc_id=str(f.resolve()),
                    text=body.strip(),
                    timestamp=timestamp,
                    source_type="markdown",
                    metadata={"path": str(f), "timestamp_source": ts_source},
                )
