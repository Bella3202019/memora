# Generalized Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Memora from a diary-only pipeline into an installable `memora` CLI that ingests files from anywhere (markdown + conversations), configured via an onboarding wizard, with a pluggable LLM backend layer defaulting to the user's Claude subscription.

**Architecture:** New modules (config loader, source adapters, LLM backends) are built inside the current `src/` tree first, each step leaving evals green. The final tasks mechanically rename `src/` → `memora/`, add `pyproject.toml` + CLI, and delete `entrypoints/`.

**Tech Stack:** Python ≥3.10, pyyaml (new), openai, neo4j, python-dotenv; optional: anthropic, google-genai; pytest for unit tests. Spec: `docs/superpowers/specs/2026-07-26-generalized-ingestion-design.md`.

## Global Constraints

- Default LLM backend is `claude-subscription` (shells out to `claude -p --output-format json`).
- Default embeddings: OpenAI-compatible, `text-embedding-3-small` (1536 dims — matches existing Neo4j indexes).
- Secrets NEVER go in `~/.memora/config.yaml` — env vars only (`OPENAI_API_KEY`, `NEO4J_PASSWORD`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`).
- Source types are exactly: `markdown`, `conversation`.
- Timestamps come from metadata (adapter fallback chain), never inferred from content by the LLM.
- Prompt content of `PROMPT_VERSIONS["v2"]` must not change (evals certify it). Preambles are prepended at call time.
- Eval suite (`python -m evals.run_extraction_eval`) must remain green after every task.
- Commits: conventional format, no Co-Authored-By, git email `velapod@gmail.com`.
- All work on branch `feature/generalized-ingestion`.
- Run tests with: `python -m pytest tests/ -v` (install once: `pip install pytest pyyaml`).

---

### Task 1: Config loader

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`
- Modify: `requirements.txt` (append `pyyaml`)

**Interfaces:**
- Produces: `load_config(path: Path | None = None) -> Config`; dataclasses `Config(user_id, sources, llm, embeddings, neo4j)`, `SourceConfig(name, type, paths, include)`, `LLMConfig(backend, base_url, model)`, `EmbeddingsConfig(base_url, model)`, `Neo4jConfig(uri, user)`; `ConfigError(Exception)`; constant `DEFAULT_CONFIG_PATH = Path.home() / ".memora" / "config.yaml"`. Env var `MEMORA_CONFIG` overrides the path.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import textwrap
import pytest
from pathlib import Path

from src.config import load_config, ConfigError, Config


VALID_YAML = textwrap.dedent("""\
    user_id: vela
    sources:
      - name: journal
        type: markdown
        paths: ["~/journal"]
      - name: chats
        type: conversation
        paths: ["~/exports"]
        include: ["**/*.json"]
    llm:
      backend: openai-compatible
      base_url: https://api.deepseek.com
      model: deepseek-chat
    neo4j:
      uri: bolt://localhost:7687
      user: neo4j
""")


def write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_load_valid_config(tmp_path):
    cfg = load_config(write(tmp_path, VALID_YAML))
    assert isinstance(cfg, Config)
    assert cfg.user_id == "vela"
    assert [s.name for s in cfg.sources] == ["journal", "chats"]
    assert cfg.sources[0].include == ["**/*.md", "**/*.txt"]  # default
    assert cfg.sources[1].include == ["**/*.json"]
    assert cfg.sources[0].paths == [str(Path("~/journal").expanduser())]
    assert cfg.llm.backend == "openai-compatible"
    assert cfg.llm.model == "deepseek-chat"


def test_defaults_applied(tmp_path):
    cfg = load_config(write(tmp_path, "sources:\n  - name: j\n    type: markdown\n    paths: ['/x']\n"))
    assert cfg.user_id == "me"
    assert cfg.llm.backend == "claude-subscription"
    assert cfg.embeddings.model == "text-embedding-3-small"
    assert cfg.neo4j.uri == "bolt://localhost:7687"


def test_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="memora init"):
        load_config(tmp_path / "nope.yaml")


def test_bad_source_type_rejected(tmp_path):
    bad = "sources:\n  - name: j\n    type: sqlite\n    paths: ['/x']\n"
    with pytest.raises(ConfigError, match="sqlite"):
        load_config(write(tmp_path, bad))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Write the implementation**

```python
# src/config.py
"""Memora configuration: ~/.memora/config.yaml loader and schema."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".memora" / "config.yaml"
SOURCE_TYPES = {"markdown", "conversation"}
DEFAULT_INCLUDE = ["**/*.md", "**/*.txt"]


class ConfigError(Exception):
    pass


@dataclass
class SourceConfig:
    name: str
    type: str
    paths: list[str]
    include: list[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE))


@dataclass
class LLMConfig:
    backend: str = "claude-subscription"
    base_url: Optional[str] = None
    model: Optional[str] = None


@dataclass
class EmbeddingsConfig:
    base_url: str = "https://api.openai.com/v1"
    model: str = "text-embedding-3-small"


@dataclass
class Neo4jConfig:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"


@dataclass
class Config:
    user_id: str
    sources: list[SourceConfig]
    llm: LLMConfig
    embeddings: EmbeddingsConfig
    neo4j: Neo4jConfig


def _source(raw: dict) -> SourceConfig:
    if raw.get("type") not in SOURCE_TYPES:
        raise ConfigError(
            f"Unknown source type {raw.get('type')!r} for source "
            f"{raw.get('name')!r}; expected one of {sorted(SOURCE_TYPES)}"
        )
    if not raw.get("paths"):
        raise ConfigError(f"Source {raw.get('name')!r} has no paths")
    return SourceConfig(
        name=raw["name"],
        type=raw["type"],
        paths=[str(Path(p).expanduser()) for p in raw["paths"]],
        include=raw.get("include") or list(DEFAULT_INCLUDE),
    )


def load_config(path: Optional[Path] = None) -> Config:
    path = Path(path or os.getenv("MEMORA_CONFIG") or DEFAULT_CONFIG_PATH)
    if not path.exists():
        raise ConfigError(
            f"No config found at {path}. Run `memora init` to create one."
        )
    raw = yaml.safe_load(path.read_text()) or {}
    return Config(
        user_id=raw.get("user_id", "me"),
        sources=[_source(s) for s in raw.get("sources", [])],
        llm=LLMConfig(**raw.get("llm", {})),
        embeddings=EmbeddingsConfig(**raw.get("embeddings", {})),
        neo4j=Neo4jConfig(**raw.get("neo4j", {})),
    )
```

Append `pyyaml` on its own line to `requirements.txt`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py requirements.txt
git commit -m "feat(config): add yaml config loader with source/llm/neo4j schema"
```

---

### Task 2: Source interface + markdown adapter

**Files:**
- Create: `src/sources/__init__.py`, `src/sources/base.py`, `src/sources/markdown.py`
- Test: `tests/test_markdown_source.py`

**Interfaces:**
- Consumes: `SourceConfig` from Task 1.
- Produces: `SourceDocument(doc_id: str, text: str, timestamp: str, source_type: str, metadata: dict)` (timestamp ISO `YYYY-MM-DDTHH:MM:SS`; `metadata["timestamp_source"]` ∈ {`filename`, `frontmatter`, `native`, `mtime`}; `metadata["path"]`); abstract `Source` with `.name`, `.prompt_preamble: str`, `.discover() -> Iterator[SourceDocument]`; factory `build_source(cfg: SourceConfig) -> Source` in `src/sources/__init__.py` (raises `ValueError` on unknown type; `conversation` registered in Task 6); `MarkdownSource`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_markdown_source.py
from src.config import SourceConfig
from src.sources import build_source
from src.sources.markdown import MarkdownSource


def make(tmp_path, include=None):
    cfg = SourceConfig(
        name="j", type="markdown", paths=[str(tmp_path)],
        include=include or ["**/*.md", "**/*.txt"],
    )
    return build_source(cfg)


def test_build_source_returns_markdown_adapter(tmp_path):
    assert isinstance(make(tmp_path), MarkdownSource)


def test_discovers_files_and_reads_text(tmp_path):
    (tmp_path / "a.md").write_text("hello world")
    (tmp_path / "skip.pdf").write_text("nope")
    docs = list(make(tmp_path).discover())
    assert len(docs) == 1
    assert docs[0].text == "hello world"
    assert docs[0].source_type == "markdown"
    assert docs[0].doc_id.endswith("a.md")


def test_timestamp_from_diary_filename(tmp_path):
    f = tmp_path / "[34B84EC6-BCB1-4652-9EFA-6BC0D9B17698]-[2026-01-04-13-01-20].md"
    f.write_text("entry")
    (doc,) = make(tmp_path).discover()
    assert doc.timestamp == "2026-01-04T13:01:20"
    assert doc.metadata["timestamp_source"] == "filename"


def test_timestamp_from_frontmatter(tmp_path):
    (tmp_path / "note.md").write_text("---\ndate: 2025-03-01\n---\nbody text")
    (doc,) = make(tmp_path).discover()
    assert doc.timestamp == "2025-03-01T00:00:00"
    assert doc.metadata["timestamp_source"] == "frontmatter"
    assert doc.text == "body text"  # frontmatter stripped


def test_timestamp_falls_back_to_mtime(tmp_path):
    (tmp_path / "plain.md").write_text("no date anywhere")
    (doc,) = make(tmp_path).discover()
    assert doc.metadata["timestamp_source"] == "mtime"
    assert len(doc.timestamp) == 19  # ISO seconds precision
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_markdown_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sources'`

- [ ] **Step 3: Write the implementation**

```python
# src/sources/base.py
"""Source adapter interface. A source discovers documents to extract from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

from src.config import SourceConfig


@dataclass
class SourceDocument:
    doc_id: str
    text: str
    timestamp: str  # ISO YYYY-MM-DDTHH:MM:SS
    source_type: str
    metadata: dict = field(default_factory=dict)


class Source(ABC):
    prompt_preamble: str = ""

    def __init__(self, config: SourceConfig):
        self.config = config
        self.name = config.name

    @abstractmethod
    def discover(self) -> Iterator[SourceDocument]:
        """Yield every document under this source's configured paths."""
```

```python
# src/sources/markdown.py
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
```

```python
# src/sources/__init__.py
from src.config import SourceConfig
from src.sources.base import Source, SourceDocument
from src.sources.markdown import MarkdownSource

_REGISTRY = {
    "markdown": MarkdownSource,
}


def build_source(cfg: SourceConfig) -> Source:
    try:
        return _REGISTRY[cfg.type](cfg)
    except KeyError:
        raise ValueError(f"Unknown source type: {cfg.type}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_markdown_source.py tests/test_config.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/sources/ tests/test_markdown_source.py
git commit -m "feat(sources): add source adapter interface and markdown adapter"
```

---

### Task 3: LLM backend layer — interface, openai-compatible, claude-subscription

**Files:**
- Create: `src/llm/__init__.py`, `src/llm/base.py`, `src/llm/openai_compat.py`, `src/llm/claude_cli.py`
- Test: `tests/test_llm_backends.py`

**Interfaces:**
- Consumes: `LLMConfig` from Task 1.
- Produces: abstract `LLMBackend` with `async complete_json(self, system: str, user: str) -> dict`; factory `get_backend(cfg: LLMConfig) -> LLMBackend` in `src/llm/__init__.py`; helper `extract_json_block(text: str) -> dict` in `src/llm/base.py` (parses JSON possibly wrapped in prose/code fences — used by claude_cli and later backends); `OpenAICompatBackend(base_url, model, api_key)`; `ClaudeCLIBackend(model=None)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_backends.py
import pytest

from src.config import LLMConfig
from src.llm import get_backend
from src.llm.base import extract_json_block
from src.llm.openai_compat import OpenAICompatBackend
from src.llm.claude_cli import ClaudeCLIBackend


def test_extract_json_block_plain():
    assert extract_json_block('{"a": 1}') == {"a": 1}


def test_extract_json_block_fenced():
    text = 'Here you go:\n```json\n{"experiences": []}\n```\nDone.'
    assert extract_json_block(text) == {"experiences": []}


def test_extract_json_block_surrounding_prose():
    assert extract_json_block('note {"x": [1, 2]} trailing') == {"x": [1, 2]}


def test_extract_json_block_invalid_raises():
    with pytest.raises(ValueError):
        extract_json_block("no json here")


def test_factory_default_is_claude_cli():
    assert isinstance(get_backend(LLMConfig()), ClaudeCLIBackend)


def test_factory_openai_compatible():
    cfg = LLMConfig(backend="openai-compatible",
                    base_url="https://api.deepseek.com", model="deepseek-chat")
    backend = get_backend(cfg)
    assert isinstance(backend, OpenAICompatBackend)
    assert backend.model == "deepseek-chat"


def test_factory_unknown_backend_raises():
    with pytest.raises(ValueError, match="nope"):
        get_backend(LLMConfig(backend="nope"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_llm_backends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.llm'`

- [ ] **Step 3: Write the implementation**

```python
# src/llm/base.py
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
```

```python
# src/llm/openai_compat.py
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
```

```python
# src/llm/claude_cli.py
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
```

```python
# src/llm/__init__.py
from src.config import LLMConfig
from src.llm.base import LLMBackend
from src.llm.claude_cli import ClaudeCLIBackend
from src.llm.openai_compat import OpenAICompatBackend


def get_backend(cfg: LLMConfig) -> LLMBackend:
    if cfg.backend == "claude-subscription":
        return ClaudeCLIBackend(model=cfg.model)
    if cfg.backend == "openai-compatible":
        return OpenAICompatBackend(
            base_url=cfg.base_url, model=cfg.model or "gpt-5.2"
        )
    raise ValueError(f"Unknown llm backend: {cfg.backend!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm_backends.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/llm/ tests/test_llm_backends.py
git commit -m "feat(llm): add backend layer with openai-compatible and claude-subscription"
```

---

### Task 4: Anthropic and Gemini native backends

**Files:**
- Create: `src/llm/anthropic_api.py`, `src/llm/gemini_api.py`
- Modify: `src/llm/__init__.py`
- Test: `tests/test_llm_backends.py` (append)
- Modify: `requirements.txt` (append comment block listing optional deps)

**Interfaces:**
- Consumes: `LLMBackend`, `extract_json_block` from Task 3.
- Produces: `AnthropicBackend(model="claude-sonnet-5")`, `GeminiBackend(model="gemini-2.5-flash")`; factory accepts `backend: anthropic` and `backend: gemini`. SDKs imported lazily inside `complete_json` so the base install works without them.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_llm_backends.py`)

```python
from src.llm.anthropic_api import AnthropicBackend
from src.llm.gemini_api import GeminiBackend


def test_factory_anthropic():
    b = get_backend(LLMConfig(backend="anthropic", model="claude-sonnet-5"))
    assert isinstance(b, AnthropicBackend)
    assert b.model == "claude-sonnet-5"


def test_factory_gemini_default_model():
    b = get_backend(LLMConfig(backend="gemini"))
    assert isinstance(b, GeminiBackend)
    assert b.model == "gemini-2.5-flash"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_llm_backends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.llm.anthropic_api'`

- [ ] **Step 3: Write the implementation**

```python
# src/llm/anthropic_api.py
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
```

```python
# src/llm/gemini_api.py
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
```

In `src/llm/__init__.py`, add imports and two factory branches before the `raise`:

```python
from src.llm.anthropic_api import AnthropicBackend
from src.llm.gemini_api import GeminiBackend
```
```python
    if cfg.backend == "anthropic":
        return AnthropicBackend(model=cfg.model or "claude-sonnet-5")
    if cfg.backend == "gemini":
        return GeminiBackend(model=cfg.model or "gemini-2.5-flash")
```

Append to `requirements.txt`:
```
# Optional LLM backends (base install works without these):
#   pip install anthropic      -> llm.backend: anthropic
#   pip install google-genai   -> llm.backend: gemini
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm_backends.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/llm/ tests/test_llm_backends.py requirements.txt
git commit -m "feat(llm): add native anthropic and gemini backends"
```

---

### Task 5: Generalize the extractor + eval `--backend` flag

**Files:**
- Modify: `src/memory/diary_extractor.py`
- Modify: `evals/run_extraction_eval.py:41-44` (imports), `:312-334` (`run_case`), `:448+` (`main` argparse)
- Test: `tests/test_extractor.py`

**Interfaces:**
- Consumes: `SourceDocument` (Task 2), `LLMBackend`/`get_backend`/`OpenAICompatBackend` (Task 3), `PROMPT_VERSIONS` (existing).
- Produces: `async extract_from_document(doc: SourceDocument, preamble: str = "", prompt_version: str = "v2", backend: LLMBackend | None = None) -> dict` (returns the extraction dict with a `source_metadata` key: `doc_id`, `timestamp`, `source_type`, `content_preview`); `extract_from_diary(...)` keeps its exact current signature plus optional `backend=None` kwarg (evals depend on it) and becomes a wrapper over `extract_from_document`. `build_prompt(preamble, prompt_version) -> str` for testability. Eval runner gains `--backend {openai-compatible,claude-subscription,anthropic,gemini}` (default `openai-compatible`, preserving current behavior) recorded in the manifest.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_extractor.py
import asyncio

from src.llm.base import LLMBackend
from src.memory.diary_extractor import build_prompt, extract_from_document
from src.prompts.diary_extraction_prompt import PROMPT_VERSIONS
from src.sources.base import SourceDocument


class FakeBackend(LLMBackend):
    def __init__(self):
        self.seen = []

    async def complete_json(self, system, user):
        self.seen.append((system, user))
        return {"experiences": [], "emotions": [], "truths": [],
                "relationships": {}}


def test_build_prompt_core_unchanged_without_preamble():
    assert build_prompt("", "v2") == PROMPT_VERSIONS["v2"]


def test_build_prompt_prepends_preamble():
    p = build_prompt("PREAMBLE TEXT", "v2")
    assert p.startswith("PREAMBLE TEXT")
    assert p.endswith(PROMPT_VERSIONS["v2"])


def test_extract_from_document_routes_through_backend():
    doc = SourceDocument(doc_id="/x/a.md", text="I went hiking.",
                         timestamp="2026-07-01T09:00:00",
                         source_type="markdown", metadata={})
    backend = FakeBackend()
    result = asyncio.run(extract_from_document(doc, backend=backend))
    assert result["source_metadata"]["doc_id"] == "/x/a.md"
    assert result["source_metadata"]["timestamp"] == "2026-07-01T09:00:00"
    (system, user) = backend.seen[0]
    assert system == PROMPT_VERSIONS["v2"]
    assert "I went hiking." in user
    assert "2026-07-01" in user
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_extractor.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_prompt'`

- [ ] **Step 3: Modify `src/memory/diary_extractor.py`**

Replace the module-level `openai_client = AsyncOpenAI(...)` (line 21) and `extract_from_diary` body with backend-routed versions. Keep `parse_diary_filename` and `load_diary` untouched. Final module content after the two kept functions:

```python
from src.llm.base import LLMBackend
from src.llm.openai_compat import OpenAICompatBackend
from src.sources.base import SourceDocument


def build_prompt(preamble: str, prompt_version: str = "v2") -> str:
    core = PROMPT_VERSIONS[prompt_version]
    return f"{preamble}\n\n{core}" if preamble else core


async def extract_from_document(
    doc: SourceDocument,
    preamble: str = "",
    prompt_version: str = "v2",
    backend: Optional[LLMBackend] = None,
) -> Dict[str, Any]:
    """Extract memories from any SourceDocument via the configured backend."""
    backend = backend or OpenAICompatBackend(base_url=None, model="gpt-5.2")
    date = doc.timestamp[:10]
    user_content = (
        f"ENTRY TO ANALYZE (Source: {doc.source_type}, "
        f"ID: {doc.doc_id}, Date: {date}):\n\n{doc.text}"
    )
    try:
        extracted = await backend.complete_json(
            build_prompt(preamble, prompt_version), user_content
        )
    except Exception as e:
        logger.error(f"Error extracting from {doc.doc_id}: {e}")
        extracted = {"experiences": [], "emotions": [], "truths": [],
                     "relationships": {}, "error": str(e)}
    extracted["source_metadata"] = {
        "doc_id": doc.doc_id,
        "timestamp": doc.timestamp,
        "source_type": doc.source_type,
        "content_preview": doc.text[:200],
    }
    return extracted


async def extract_from_diary(
    diary_id: str,
    diary_date: str,
    content: str,
    prompt_version: str = "v2",
    model: str = "gpt-5.2",
    backend: Optional[LLMBackend] = None,
) -> Dict[str, Any]:
    """Back-compat wrapper used by evals and the legacy entrypoint."""
    doc = SourceDocument(
        doc_id=diary_id, text=content,
        timestamp=f"{diary_date}T00:00:00", source_type="markdown",
        metadata={},
    )
    backend = backend or OpenAICompatBackend(base_url=None, model=model)
    result = await extract_from_document(
        doc, prompt_version=prompt_version, backend=backend
    )
    result["diary_metadata"] = {
        "diary_id": diary_id,
        "diary_date": diary_date,
        "content_preview": content[:200] if content else "",
    }
    return result
```

Remove the now-unused `openai_client`, `AsyncOpenAI` import, and old `extract_from_diary` body. Keep the `re`, `os`, `json` imports only if still used (`re` is — by `parse_diary_filename`).

- [ ] **Step 4: Add `--backend` to the eval runner**

In `evals/run_extraction_eval.py`:
- Add import: `from src.llm import get_backend` and `from src.config import LLMConfig`.
- In `main()`'s argparse block add:
```python
    parser.add_argument(
        "--backend",
        choices=["openai-compatible", "claude-subscription", "anthropic", "gemini"],
        default="openai-compatible",
        help="LLM backend for the extractor (default preserves current behavior)",
    )
```
- Build the backend once in `main()` and thread it through `run_trial` → `run_case` → `extract_from_diary(..., backend=backend)`:
```python
    backend = get_backend(LLMConfig(backend=args.backend, model=args.model))
```
  (`run_case(case, prompt_version, model, backend)` and `run_trial(cases, prompt_version, model, backend)` gain a trailing parameter; the `extract_from_diary` call adds `backend=backend`.)
- In `build_manifest`, record it: add `"backend": args.backend,` next to the extractor model field.

- [ ] **Step 5: Run tests + eval smoke check**

Run: `python -m pytest tests/ -v`
Expected: all pass
Run: `python -m evals.run_extraction_eval --case dream-boundary --prompt-version v2`
Expected: completes with same-quality result as before (requires `OPENAI_API_KEY` + `DEEPSEEK_API_KEY`; if keys unavailable, verify `python -m evals.run_extraction_eval --help` shows `--backend` and imports succeed)

- [ ] **Step 6: Commit**

```bash
git add src/memory/diary_extractor.py evals/run_extraction_eval.py tests/test_extractor.py
git commit -m "feat(extractor): route extraction through backend layer, add eval --backend"
```

---

### Task 6: Conversation adapter

**Files:**
- Create: `src/sources/conversation.py`
- Modify: `src/sources/__init__.py` (register type)
- Test: `tests/test_conversation_source.py`

**Interfaces:**
- Consumes: `Source`, `SourceDocument` (Task 2), `SourceConfig` (Task 1).
- Produces: `ConversationSource` registered as type `conversation`. Accepts: ChatGPT export JSON (list of conversations with `mapping`), Claude export JSON (list with `chat_messages`), plain-text speaker-labeled transcripts (`.txt`/`.md`). One `SourceDocument` per conversation; text formatted as `[User]: ...` / `[Assistant]: ...` lines (matching `voice/src/memory/call_extractor.py`'s convention). `prompt_preamble` states the two-party rule.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_conversation_source.py
import json

from src.config import SourceConfig
from src.sources import build_source
from src.sources.conversation import ConversationSource

CHATGPT_EXPORT = [{
    "title": "Trip planning",
    "create_time": 1751364000.0,  # 2025-07-01 UTC
    "mapping": {
        "n1": {"message": {"author": {"role": "user"},
                            "content": {"parts": ["I want to visit Kyoto"]}}},
        "n2": {"message": {"author": {"role": "assistant"},
                            "content": {"parts": ["Great choice!"]}}},
        "n3": {"message": None},
    },
}]

CLAUDE_EXPORT = [{
    "name": "Career chat",
    "created_at": "2025-06-15T10:30:00Z",
    "chat_messages": [
        {"sender": "human", "text": "I got promoted today"},
        {"sender": "assistant", "text": "Congratulations!"},
    ],
}]


def make(tmp_path, include):
    cfg = SourceConfig(name="c", type="conversation",
                       paths=[str(tmp_path)], include=include)
    return build_source(cfg)


def test_registered_in_factory(tmp_path):
    assert isinstance(make(tmp_path, ["**/*.json"]), ConversationSource)


def test_preamble_mentions_user_only(tmp_path):
    pre = ConversationSource.prompt_preamble
    assert "USER" in pre and "assistant" in pre.lower()


def test_chatgpt_export(tmp_path):
    (tmp_path / "conversations.json").write_text(json.dumps(CHATGPT_EXPORT))
    (doc,) = make(tmp_path, ["**/*.json"]).discover()
    assert doc.source_type == "conversation"
    assert "[User]: I want to visit Kyoto" in doc.text
    assert "[Assistant]: Great choice!" in doc.text
    assert doc.timestamp.startswith("2025-07-01")
    assert doc.metadata["timestamp_source"] == "native"
    assert doc.doc_id.endswith("conversations.json#0")


def test_claude_export(tmp_path):
    (tmp_path / "conversations.json").write_text(json.dumps(CLAUDE_EXPORT))
    (doc,) = make(tmp_path, ["**/*.json"]).discover()
    assert "[User]: I got promoted today" in doc.text
    assert doc.timestamp == "2025-06-15T10:30:00"


def test_plain_text_transcript(tmp_path):
    (tmp_path / "call.txt").write_text("User: hello\nAgent: hi there\n")
    (doc,) = make(tmp_path, ["**/*.txt"]).discover()
    assert "[User]: hello" in doc.text
    assert doc.metadata["timestamp_source"] == "mtime"


def test_unparseable_json_skipped(tmp_path):
    (tmp_path / "bad.json").write_text("{not json")
    assert list(make(tmp_path, ["**/*.json"]).discover()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_conversation_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sources.conversation'`

- [ ] **Step 3: Write the implementation**

```python
# src/sources/conversation.py
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
```

Register in `src/sources/__init__.py`:

```python
from src.sources.conversation import ConversationSource

_REGISTRY = {
    "markdown": MarkdownSource,
    "conversation": ConversationSource,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass (6 new)

- [ ] **Step 5: Commit**

```bash
git add src/sources/ tests/test_conversation_source.py
git commit -m "feat(sources): add conversation adapter for chat exports and transcripts"
```

---

### Task 7: Ingest orchestration with incremental state

**Files:**
- Create: `src/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `Config`/`SourceConfig` (Task 1), `build_source` (Tasks 2/6), `extract_from_document` (Task 5), `get_backend` (Task 3), existing `MemoryStorage.store_extracted_data(user_id, extracted_data, call_id)` from `src/memory/storage.py:340`.
- Produces: `async ingest(config: Config, source_name: str | None = None, dry_run: bool = False, state_path: Path | None = None) -> dict` returning `{"total", "processed", "skipped", "errors", "details"}`; `IngestState(path)` with `.is_processed(doc_id, text) -> bool`, `.mark(doc_id, text) -> None` (JSON file `{doc_id: sha256(text)}`, default `~/.memora/state/ingest.json`). CLI (Task 8) calls `ingest`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ingest.py
import asyncio
import json

from src.config import Config, SourceConfig, LLMConfig, EmbeddingsConfig, Neo4jConfig
from src.ingest import IngestState, ingest
from src.llm.base import LLMBackend


class FakeBackend(LLMBackend):
    async def complete_json(self, system, user):
        return {"experiences": [], "emotions": [], "truths": [],
                "relationships": {}}


def make_config(tmp_path):
    return Config(
        user_id="t",
        sources=[SourceConfig(name="j", type="markdown",
                              paths=[str(tmp_path / "docs")])],
        llm=LLMConfig(), embeddings=EmbeddingsConfig(), neo4j=Neo4jConfig(),
    )


def test_state_roundtrip(tmp_path):
    state = IngestState(tmp_path / "state.json")
    assert not state.is_processed("a", "text")
    state.mark("a", "text")
    assert state.is_processed("a", "text")
    assert not state.is_processed("a", "EDITED text")  # content changed
    reloaded = IngestState(tmp_path / "state.json")
    assert reloaded.is_processed("a", "text")


def test_dry_run_extracts_without_marking(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("I hiked today with Sam.")
    cfg = make_config(tmp_path)
    state_path = tmp_path / "state.json"
    summary = asyncio.run(ingest(cfg, dry_run=True, state_path=state_path,
                                 backend=FakeBackend()))
    assert summary["processed"] == 1
    assert summary["errors"] == 0
    # dry run must not mark anything processed
    summary2 = asyncio.run(ingest(cfg, dry_run=True, state_path=state_path,
                                  backend=FakeBackend()))
    assert summary2["processed"] == 1


def test_unknown_source_name(tmp_path):
    cfg = make_config(tmp_path)
    (tmp_path / "docs").mkdir()
    summary = asyncio.run(ingest(cfg, source_name="nope", dry_run=True,
                                 state_path=tmp_path / "s.json",
                                 backend=FakeBackend()))
    assert summary["total"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingest'`

- [ ] **Step 3: Write the implementation**

```python
# src/ingest.py
"""Ingest pipeline: discover documents from configured sources, extract, store."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from src.config import Config
from src.llm import get_backend
from src.llm.base import LLMBackend
from src.memory.diary_extractor import extract_from_document
from src.sources import build_source

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path.home() / ".memora" / "state" / "ingest.json"
MIN_CONTENT_LENGTH = 10


class IngestState:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or DEFAULT_STATE_PATH)
        self._seen: dict = {}
        if self.path.exists():
            self._seen = json.loads(self.path.read_text())

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def is_processed(self, doc_id: str, text: str) -> bool:
        return self._seen.get(doc_id) == self._hash(text)

    def mark(self, doc_id: str, text: str) -> None:
        self._seen[doc_id] = self._hash(text)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._seen, indent=2))


async def ingest(
    config: Config,
    source_name: Optional[str] = None,
    dry_run: bool = False,
    state_path: Optional[Path] = None,
    backend: Optional[LLMBackend] = None,
) -> dict:
    backend = backend or get_backend(config.llm)
    state = IngestState(state_path)
    summary = {"total": 0, "processed": 0, "skipped": 0, "errors": 0,
               "details": []}

    sources = [
        build_source(s) for s in config.sources
        if source_name is None or s.name == source_name
    ]
    if source_name and not sources:
        logger.warning(f"No source named {source_name!r} in config")

    for source in sources:
        for doc in source.discover():
            summary["total"] += 1
            if len(doc.text.strip()) < MIN_CONTENT_LENGTH:
                summary["skipped"] += 1
                summary["details"].append(
                    {"doc": doc.doc_id, "status": "skipped", "reason": "too short"})
                continue
            if not dry_run and state.is_processed(doc.doc_id, doc.text):
                summary["skipped"] += 1
                summary["details"].append(
                    {"doc": doc.doc_id, "status": "skipped",
                     "reason": "already processed"})
                continue
            try:
                extracted = await extract_from_document(
                    doc, preamble=source.prompt_preamble, backend=backend
                )
                if not dry_run:
                    # Local import: Neo4j connection only needed when storing
                    from src.memory.storage import MemoryStorage
                    await MemoryStorage().store_extracted_data(
                        user_id=config.user_id,
                        extracted_data={
                            "experiences": extracted.get("experiences", []),
                            "emotions": extracted.get("emotions", []),
                            "truths": extracted.get("truths", []),
                            "relationships": extracted.get("relationships", {}),
                            "message_metadata": {"timestamp": doc.timestamp},
                        },
                        call_id=doc.doc_id,
                    )
                    state.mark(doc.doc_id, doc.text)
                summary["processed"] += 1
                summary["details"].append({
                    "doc": doc.doc_id, "status": "processed",
                    "experiences": len(extracted.get("experiences", [])),
                    "emotions": len(extracted.get("emotions", [])),
                    "truths": len(extracted.get("truths", [])),
                })
            except Exception as e:
                logger.error(f"Error processing {doc.doc_id}: {e}")
                summary["errors"] += 1
                summary["details"].append(
                    {"doc": doc.doc_id, "status": "error", "error": str(e)})
    return summary
```

Note for the implementer: `ingest()` takes an optional `backend` kwarg (used by tests with `FakeBackend`) — it IS part of the produced interface even though the spec's summary omits it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): add source-driven ingest pipeline with incremental state"
```

---

### Task 8: Package rename `src/` → `memora/`, pyproject, CLI skeleton

**Files:**
- Rename: `src/` → `memora/`; `entrypoints/mcp_server.py` → `memora/mcp/server.py`
- Create: `pyproject.toml`, `memora/cli.py`, `memora/mcp/__init__.py`
- Delete: `entrypoints/` (all of: `extract_diary_memories.py`, `chat.py`, `mcp_server.py`, `__init__.py` if present)
- Modify: every `from src.` import in `memora/**` and `evals/**` and `tests/**` → `from memora.`
- Test: existing suite + `memora --help`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: console command `memora` with subcommands `init` (stub this task, wizard in Task 9), `ingest [--source NAME] [--dry-run] [--config PATH]`, `chat`, `mcp`. `main()` in `memora/cli.py` is the `[project.scripts]` entry.

- [ ] **Step 1: Mechanical rename**

```bash
git mv src memora
mkdir -p memora/mcp memora/resources
git mv entrypoints/mcp_server.py memora/mcp/server.py
touch memora/mcp/__init__.py memora/resources/__init__.py
cp docker-compose.yml memora/resources/docker-compose.yml   # bundled for `memora init` auto-start; root copy stays canonical for repo dev
git rm entrypoints/extract_diary_memories.py entrypoints/chat.py
# if entrypoints/__init__.py exists: git rm entrypoints/__init__.py
grep -rl "from src\.\|import src\." memora evals tests | xargs sed -i '' 's/from src\./from memora./g; s/import src\./import memora./g'
grep -rn "from src\.\|import src\." memora evals tests memora/mcp/server.py
```
Expected final grep: no matches. Also check `memora/mcp/server.py` and `memora/agents/chat_agent.py` for `sys.path.insert` hacks referencing the old layout and remove them.

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "memora"
version = "0.1.0"
description = "Personal memory graph: extract experiences, emotions, and truths from your files into Neo4j"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "python-dotenv",
    "neo4j",
    "openai",
    "pyyaml",
]

[project.optional-dependencies]
anthropic = ["anthropic"]
gemini = ["google-genai"]
dev = ["pytest"]

[project.scripts]
memora = "memora.cli:main"

[tool.setuptools.packages.find]
include = ["memora*"]

[tool.setuptools.package-data]
"memora.resources" = ["docker-compose.yml"]
```

- [ ] **Step 3: Write `memora/cli.py`**

```python
# memora/cli.py
"""memora CLI: init / ingest / chat / mcp."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from memora.config import ConfigError, load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def cmd_ingest(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    from memora.ingest import ingest
    summary = asyncio.run(ingest(
        config, source_name=args.source, dry_run=args.dry_run
    ))
    print(f"\nTotal: {summary['total']}  Processed: {summary['processed']}  "
          f"Skipped: {summary['skipped']}  Errors: {summary['errors']}")
    return 1 if summary["errors"] else 0


def cmd_chat(args) -> int:
    from memora.agents.chat_agent import run_chat_loop
    asyncio.run(run_chat_loop())
    return 0


def cmd_mcp(args) -> int:
    from memora.mcp.server import main as mcp_main
    mcp_main()
    return 0


def cmd_init(args) -> int:
    from memora.init_wizard import run_wizard
    return run_wizard(args.config)


def main() -> None:
    parser = argparse.ArgumentParser(prog="memora",
                                     description="Personal memory graph")
    parser.add_argument("--config", type=Path, default=None,
                        help="Path to config.yaml (default ~/.memora/config.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Interactive setup wizard")
    p_ingest = sub.add_parser("ingest", help="Extract and store memories")
    p_ingest.add_argument("--source", help="Only this named source")
    p_ingest.add_argument("--dry-run", action="store_true",
                          help="Extract but don't store")
    sub.add_parser("chat", help="Chat with your memory graph")
    sub.add_parser("mcp", help="Run the MCP server (stdio)")

    args = parser.parse_args()
    handler = {"init": cmd_init, "ingest": cmd_ingest,
               "chat": cmd_chat, "mcp": cmd_mcp}[args.command]
    sys.exit(handler(args))
```

Implementation notes:
- `entrypoints/chat.py` (75 lines) had the REPL loop — move that loop into `memora/agents/chat_agent.py` as `async def run_chat_loop()` (copy the input/print loop verbatim, adjusting imports), since `entrypoints/chat.py` is deleted.
- `memora/mcp/server.py`: wrap its existing `if __name__ == "__main__":` body in a `def main() -> None:` and call it from the guard, so `cmd_mcp` can import it.
- `memora/init_wizard.py` does not exist yet — Task 9 creates it. For this task, create a 3-line stub so `memora init` prints "wizard coming in next commit" and returns 1. Replace in Task 9.

```python
# memora/init_wizard.py  (stub, replaced in Task 9)
def run_wizard(config_path=None) -> int:
    print("memora init: wizard not implemented yet")
    return 1
```

- [ ] **Step 4: Install and verify**

```bash
pip install -e .
python -m pytest tests/ -v          # all pass with new import paths
memora --help                        # shows init/ingest/chat/mcp
memora ingest --dry-run 2>&1 | head -3   # ConfigError message mentions `memora init` (if no config)
python -m evals.run_extraction_eval --help   # imports still work
```

- [ ] **Step 5: Commit**

```bash
git add -u
git add pyproject.toml memora/cli.py memora/init_wizard.py memora/mcp/__init__.py memora/resources/
git commit -m "refactor: rename src to memora package with installable CLI"
```
(Exception to the no-`git add -u` habit is deliberate here: the rename touches every moved file; verify with `git status` that only renames/import rewrites are staged before committing.)

---

### Task 9: `memora init` onboarding wizard

**Files:**
- Create: `memora/init_wizard.py` (replace stub)
- Test: `tests/test_init_wizard.py`

**Interfaces:**
- Consumes: `Config` schema (Task 1), `build_source` (Tasks 2/6), `DEFAULT_CONFIG_PATH`.
- Produces: `run_wizard(config_path: Path | None = None, input_fn=input, print_fn=print, which_fn=shutil.which) -> int` — `input_fn`/`print_fn`/`which_fn` injectable for tests (tests pass `which_fn=lambda _: None` so the Docker offer never fires). Writes YAML config; re-running loads the existing config and appends sources. Helpers: `check_environment(backend: str, print_fn) -> None` (claude CLI present / ANTHROPIC_API_KEY warning / OPENAI_API_KEY for embeddings) and `_start_local_neo4j(print_fn) -> None` (runs the compose file bundled at `memora/resources/docker-compose.yml` via `docker compose -p memora up -d`, then polls port 7687 until Neo4j accepts connections, max 120s).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_init_wizard.py
import yaml

from memora.init_wizard import run_wizard


def scripted(answers):
    it = iter(answers)
    return lambda prompt="": next(it)


def test_wizard_writes_config(tmp_path):
    docs = tmp_path / "journal"
    docs.mkdir()
    (docs / "a.md").write_text("hello")
    config_path = tmp_path / "config.yaml"
    answers = [
        "vela",            # user id
        "1",               # source type: markdown
        str(docs),         # path
        "",                # include glob (accept default)
        "journal",         # source name
        "n",               # add another source?
        "",                # neo4j uri (accept default)
        "",                # neo4j user (accept default)
        "1",               # llm backend: claude-subscription (default)
        "",                # embeddings (accept default)
    ]
    rc = run_wizard(config_path, input_fn=scripted(answers),
                    print_fn=lambda *a, **k: None,
                    which_fn=lambda _: None)  # no docker offer in tests
    assert rc == 0
    cfg = yaml.safe_load(config_path.read_text())
    assert cfg["user_id"] == "vela"
    assert cfg["sources"][0] == {
        "name": "journal", "type": "markdown",
        "paths": [str(docs)], "include": ["**/*.md", "**/*.txt"],
    }
    assert cfg["llm"]["backend"] == "claude-subscription"
    assert cfg["neo4j"]["uri"] == "bolt://localhost:7687"


def test_wizard_rerun_appends_source(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "user_id": "vela",
        "sources": [{"name": "old", "type": "markdown",
                     "paths": ["/tmp/x"], "include": ["**/*.md"]}],
        "llm": {"backend": "claude-subscription"},
    }))
    docs = tmp_path / "chats"
    docs.mkdir()
    answers = [
        "y",               # keep existing user id + sources, add more?
        "2",               # source type: conversation
        str(docs),         # path
        "",                # include glob default for conversation (**/*.json)
        "chats",           # name
        "n",               # add another?
        "", "", "1", "",   # neo4j x2, backend, embeddings
    ]
    rc = run_wizard(config_path, input_fn=scripted(answers),
                    print_fn=lambda *a, **k: None,
                    which_fn=lambda _: None)  # no docker offer in tests
    assert rc == 0
    cfg = yaml.safe_load(config_path.read_text())
    assert [s["name"] for s in cfg["sources"]] == ["old", "chats"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_init_wizard.py -v`
Expected: FAIL — stub returns 1 / TypeError on kwargs

- [ ] **Step 3: Write the implementation**

```python
# memora/init_wizard.py
"""`memora init`: interactive onboarding wizard. Plain input(), no TUI deps."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from importlib import resources
from pathlib import Path
from typing import Callable, Optional

import yaml

from memora.config import DEFAULT_CONFIG_PATH, SourceConfig, DEFAULT_INCLUDE
from memora.sources import build_source

SOURCE_MENU = {"1": "markdown", "2": "conversation"}
BACKEND_MENU = {
    "1": "claude-subscription",
    "2": "openai-compatible",
    "3": "anthropic",
    "4": "gemini",
}
CONVERSATION_INCLUDE = ["**/*.json", "**/*.txt"]


def _ask(input_fn, prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input_fn(f"{prompt}{suffix}: ").strip()
    return answer or default


def _preview_source(cfg: SourceConfig, print_fn) -> None:
    try:
        docs = list(build_source(cfg).discover())
    except Exception as e:
        print_fn(f"  ! could not scan {cfg.paths}: {e}")
        return
    if docs:
        newest = max(d.timestamp for d in docs)
        print_fn(f"  ✓ found {len(docs)} documents, newest: {newest[:10]}")
    else:
        print_fn("  ! found 0 documents — check the path and include pattern")


def _start_local_neo4j(print_fn) -> None:
    """Start the bundled docker-compose Neo4j and wait for bolt to accept."""
    with resources.as_file(
        resources.files("memora.resources") / "docker-compose.yml"
    ) as compose:
        subprocess.run(
            ["docker", "compose", "-f", str(compose), "-p", "memora",
             "up", "-d"],
            check=True,
        )
    print_fn("  waiting for Neo4j to accept connections...")
    for _ in range(60):
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex(("localhost", 7687)) == 0:
                print_fn("  ✓ Neo4j is up at bolt://localhost:7687")
                return
        time.sleep(2)
    print_fn("  ! Neo4j did not come up in 120s — check "
             "`docker compose -p memora ps`")


def check_environment(backend: str, print_fn) -> None:
    if backend == "claude-subscription":
        if shutil.which("claude") is None:
            print_fn("  ! `claude` CLI not found — install Claude Code and log in")
        elif os.getenv("ANTHROPIC_API_KEY"):
            print_fn("  ! ANTHROPIC_API_KEY is set: `claude -p` will bill the "
                     "API, not your subscription. Unset it to use plan credit.")
        else:
            print_fn("  ✓ claude CLI found")
    if backend in ("openai-compatible",):
        print_fn("  ✓ OPENAI_API_KEY set" if os.getenv("OPENAI_API_KEY")
                 else "  ! OPENAI_API_KEY not set")
    if backend == "anthropic":
        print_fn("  ✓ ANTHROPIC_API_KEY set" if os.getenv("ANTHROPIC_API_KEY")
                 else "  ! ANTHROPIC_API_KEY not set")
    if backend == "gemini":
        print_fn("  ✓ GEMINI_API_KEY set" if os.getenv("GEMINI_API_KEY")
                 else "  ! GEMINI_API_KEY not set")
    # Embeddings always need an OpenAI-compatible key (or local Ollama)
    print_fn("  note: embeddings need OPENAI_API_KEY — or point "
             "embeddings.base_url at Ollama (http://localhost:11434/v1) "
             "with model nomic-embed-text for fully local")


def run_wizard(
    config_path: Optional[Path] = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable = print,
    which_fn: Callable[[str], Optional[str]] = shutil.which,
) -> int:
    path = Path(config_path or DEFAULT_CONFIG_PATH)
    existing: dict = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text()) or {}
        print_fn(f"Existing config found at {path}")
        keep = _ask(input_fn, "Keep it and add more sources? (y/n)", "y")
        if keep.lower() != "y":
            existing = {}

    print_fn("Welcome to Memora. Let's set up your memory sources.\n")

    user_id = existing.get("user_id") or _ask(input_fn, "Your user id", "me")
    sources = list(existing.get("sources", []))

    while True:
        print_fn("Source type:  1) markdown/text notes  2) conversation "
                 "(chat exports / call transcripts)")
        stype = SOURCE_MENU.get(_ask(input_fn, "Choose", "1"), "markdown")
        spath = _ask(input_fn, "Where do these files live? (path)")
        default_include = (" ".join(CONVERSATION_INCLUDE)
                           if stype == "conversation"
                           else " ".join(DEFAULT_INCLUDE))
        include = _ask(input_fn, "Include which files?", default_include).split()
        name = _ask(input_fn, "Name this source", stype)
        src = {"name": name, "type": stype,
               "paths": [str(Path(spath).expanduser())], "include": include}
        _preview_source(SourceConfig(**src), print_fn)
        sources.append(src)
        if _ask(input_fn, "Add another source? (y/n)", "n").lower() != "y":
            break

    print_fn("\nNeo4j — local Docker (default) or a Neo4j Aura URI "
             "(neo4j+s://...). Password is read from NEO4J_PASSWORD.")
    neo4j_uri = _ask(input_fn, "Neo4j URI", "bolt://localhost:7687")
    neo4j_user = _ask(input_fn, "Neo4j user", "neo4j")
    if neo4j_uri == "bolt://localhost:7687" and which_fn("docker"):
        if _ask(input_fn, "Start local Neo4j via Docker now? (y/n)",
                "y").lower() == "y":
            _start_local_neo4j(print_fn)

    print_fn("\nLLM backend:  1) claude-subscription (default, uses your "
             "Claude plan)  2) openai-compatible  3) anthropic  4) gemini")
    backend = BACKEND_MENU.get(_ask(input_fn, "Choose", "1"),
                               "claude-subscription")
    llm: dict = {"backend": backend}
    if backend == "openai-compatible":
        llm["base_url"] = _ask(input_fn, "Base URL",
                               "https://api.openai.com/v1")
        llm["model"] = _ask(input_fn, "Model", "gpt-5.2")

    embeddings_model = _ask(input_fn, "Embeddings model",
                            "text-embedding-3-small")

    check_environment(backend, print_fn)

    config = {
        "user_id": user_id,
        "sources": sources,
        "llm": llm,
        "embeddings": {"base_url": "https://api.openai.com/v1",
                       "model": embeddings_model},
        "neo4j": {"uri": neo4j_uri, "user": neo4j_user},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    print_fn(f"\n✓ Wrote {path}")
    print_fn("Next: run `memora ingest --dry-run` to preview extraction.")
    return 0
```

Note: Task 1's `src/config.py` (now `memora/config.py`) must export `DEFAULT_INCLUDE` — it already does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass. Then manually: `memora init --config /tmp/memora-test.yaml` and walk through once against a real directory.

- [ ] **Step 5: Commit**

```bash
git add memora/init_wizard.py tests/test_init_wizard.py
git commit -m "feat(cli): add memora init onboarding wizard"
```

---

### Task 10: README rewrite + embedder config

**Files:**
- Modify: `README.md` (rewrite Quick Start / usage sections), `memora/memory/embedder.py:12-16`
- Test: manual review + `python -m pytest tests/ -v`

**Interfaces:**
- Consumes: everything shipped in Tasks 1–9.
- Produces: README describing the new UX; embedder reads `embeddings` config instead of hardcoding OpenAI.

- [ ] **Step 1: Make the embedder config-aware**

In `memora/memory/embedder.py`, replace the hardcoded client/model (lines 12-16) with:

```python
from memora.config import DEFAULT_CONFIG_PATH, EmbeddingsConfig, load_config


def _embeddings_config() -> EmbeddingsConfig:
    try:
        return load_config().embeddings
    except Exception:
        return EmbeddingsConfig()  # config optional: default OpenAI


_cfg = _embeddings_config()
EMBEDDING_MODEL = _cfg.model
_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY") or "unused",
                      base_url=_cfg.base_url)
```

Keep `EMBEDDING_DIMENSIONS = 1536` and the note that non-default embedding models need matching index dimensions (add one comment line: `# Non-default models: recreate vector indexes with the model's dimension.`).

- [ ] **Step 2: Rewrite README sections**

Replace the setup/usage portions of `README.md` (keep the eval results, memory-type table, and schema sections). New content to include verbatim:

````markdown
## Quick Start

```bash
pip install -e .
docker compose up -d          # local Neo4j (or use Neo4j Aura free tier)
memora init                   # onboarding wizard: sources, backend, database
memora ingest --dry-run       # preview what would be extracted
memora ingest                 # extract and store memories
memora chat                   # talk to your memory graph
memora mcp                    # expose it to Claude Desktop / Cursor via MCP
```

## Configuring sources

Memora ingests files from anywhere on your machine. Two source types:

- **markdown** — diaries, notes, Obsidian vaults (`.md`/`.txt`)
- **conversation** — ChatGPT/Claude export JSON, speaker-labeled call transcripts

`memora init` writes `~/.memora/config.yaml`; edit it by hand any time:

```yaml
user_id: me
sources:
  - name: journal
    type: markdown
    paths: [~/Documents/journal]
    include: ["**/*.md"]
  - name: chatgpt
    type: conversation
    paths: [~/Downloads/chatgpt-export]
llm:
  backend: claude-subscription   # default: your Claude plan, no API bill
embeddings:
  model: text-embedding-3-small  # needs OPENAI_API_KEY
neo4j:
  uri: bolt://localhost:7687
  user: neo4j                    # password from NEO4J_PASSWORD
```

Timestamps are resolved per document: native timestamps (chat exports) →
filename patterns → markdown front-matter `date:` → file modified time.
Never inferred from content by the LLM.

## LLM backends

| backend | auth | notes |
|---|---|---|
| `claude-subscription` (default) | Claude Code login | shells out to `claude -p`; zero marginal cost on your plan. Do NOT set `ANTHROPIC_API_KEY` or the CLI bills the API instead. |
| `openai-compatible` | `OPENAI_API_KEY` + `base_url` | OpenAI, DeepSeek, Ollama, OpenRouter, Groq |
| `anthropic` | `ANTHROPIC_API_KEY` | `pip install anthropic` |
| `gemini` | `GEMINI_API_KEY` | `pip install google-genai` |

Extraction quality (F1 0.926, hallucination rate, below) is certified for
`gpt-5.2` only. Measure any backend yourself:

```bash
python -m evals.run_extraction_eval --backend claude-subscription --trials 3
```

## Fully local setup

No API keys, nothing leaves your machine: Docker Neo4j + Ollama.

```yaml
llm:
  backend: openai-compatible
  base_url: http://localhost:11434/v1
  model: llama3.1
embeddings:
  base_url: http://localhost:11434/v1
  model: nomic-embed-text      # note: 768 dims — recreate vector indexes to match
```
````

Also update the project-structure diagram in the README to the `memora/` layout and delete references to `entrypoints/` and `python -m entrypoints.*` commands (the MCP config example becomes `"command": "memora", "args": ["mcp"]`).

- [ ] **Step 3: Full verification pass**

```bash
python -m pytest tests/ -v                       # all pass
memora --help
python -m evals.run_extraction_eval --trials 1   # full eval run; F1 must match v2 baseline (~0.93)
```

- [ ] **Step 4: Commit**

```bash
git add README.md memora/memory/embedder.py
git commit -m "docs: rewrite README for installable CLI and configurable backends"
```

---

## Final acceptance checklist

- [ ] `pip install -e .` on a clean venv → `memora init` → `memora ingest --dry-run` works end-to-end on a sample directory
- [ ] `python -m evals.run_extraction_eval --trials 1` matches the v2 baseline (mean F1 ≈ 0.93; the extraction path change is routing-only)
- [ ] `memora mcp` responds to an `initialize` JSON-RPC request on stdin
- [ ] `git status` clean; every commit conventional-format, email `velapod@gmail.com`
