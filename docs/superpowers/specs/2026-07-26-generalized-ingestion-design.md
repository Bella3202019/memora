# Generalized Ingestion — Design Spec

**Date:** 2026-07-26
**Status:** Approved design, pending implementation plan
**Project:** 1 of 3 in the open-source launch effort (2: voice bot on Memora, 3: memory-science positioning docs)

## Goal

Turn Memora from a diary-only pipeline into a general personal memory graph: users point it at files anywhere on their filesystem, configured through an onboarding wizard, powered by a configurable LLM backend — packaged as an installable `memora` CLI suitable for a public open-source release.

## Non-Goals (this project)

- New eval cases for the conversation preamble (separate follow-up)
- File watching / continuous ingestion
- Non-file sources (APIs, email, browser history)
- OpenAI-subscription (ChatGPT plan credit) backend — roadmap note only; no clean mechanism today
- Changes to the voice agents (project 2) or positioning docs (project 3)

## 1. Package Layout

`src/` becomes an installable package; `entrypoints/` is deleted.

```
memora/
├── cli.py               # memora init / ingest / chat / mcp
├── config.py            # config load + validation
├── sources/
│   ├── base.py          # Source interface + SourceDocument
│   ├── markdown.py      # .md/.txt in user directories
│   └── conversation.py  # ChatGPT/Claude exports + call transcripts (two-party dialogues)
├── llm/
│   ├── base.py          # LLMBackend interface (one method: structured JSON completion)
│   ├── openai_compat.py # base_url + model + key (OpenAI, DeepSeek, Ollama, OpenRouter, Groq)
│   ├── claude_cli.py    # claude -p --output-format json (subscription; DEFAULT)
│   ├── anthropic_api.py # native Anthropic SDK
│   └── gemini_api.py    # native Google SDK
├── memory/              # client, storage, embedder, retriever (moved, imports updated)
├── prompts/             # shared core prompt + per-source preambles
├── agents/              # chat agent
└── mcp/server.py        # moved from entrypoints/mcp_server.py
```

- `pyproject.toml` with a `memora` console script; `pip install memora` (or `pip install -e .`) and go.
- Evals update imports in the same pass; eval behavior and dataset unchanged.
- Migration is executed in safe steps: adapters + config land inside the current tree first (evals green after each step), then the package rename + CLI as a final mechanical commit.

## 2. Configuration

File: `~/.memora/config.yaml` (override with `--config` or `MEMORA_CONFIG`). Secrets never live in the config — only env vars (`OPENAI_API_KEY`, `NEO4J_PASSWORD`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`), so the config is safe to paste into bug reports.

```yaml
sources:
  - name: journal
    type: markdown            # markdown | conversation
    paths: [~/Documents/journal]
    include: ["**/*.md"]
  - name: chatgpt
    type: conversation
    paths: [~/Downloads/chatgpt-export]

llm:
  backend: claude-subscription   # DEFAULT. also: openai-compatible | anthropic | gemini
  # backend: openai-compatible
  # base_url: https://api.deepseek.com   # any OpenAI-compatible endpoint
  # model: deepseek-chat

embeddings:
  base_url: https://api.openai.com/v1    # OpenAI-compatible only (incl. Ollama for local)
  model: text-embedding-3-small          # DEFAULT; 1536 dims matches existing indexes

neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  # password from NEO4J_PASSWORD
```

## 3. Onboarding: `memora init`

A plain-`input()` CLI wizard (no TUI dependency). Flow:

1. **Sources loop** — for each source: pick type → enter path(s) → confirm include glob (default shown) → name it. The wizard immediately runs `discover()` and shows "found N files, newest: DATE" so path typos surface instantly. Repeat until done.
2. **Neo4j** — offer two paths:
   - **Local (default):** if Docker is available, offer to start the bundled `docker-compose.yml`, wait for the healthcheck, and fill in `bolt://localhost:7687` automatically.
   - **Hosted:** accept a Neo4j Aura `neo4j+s://` URI + user (password via env).
3. **LLM backend** — default `claude-subscription`. The wizard:
   - verifies the `claude` CLI is installed and logged in;
   - **warns if `ANTHROPIC_API_KEY` is set** (the CLI would silently bill the API instead of the subscription);
   - offers the other backends (openai-compatible / anthropic / gemini) as alternatives.
4. **Embeddings** — default OpenAI `text-embedding-3-small`; checks `OPENAI_API_KEY`. States explicitly: "an OpenAI key is needed only for embeddings — or point at Ollama (`nomic-embed-text`) for fully local" (Ollama uses a different dimension; the index is created to match the configured model's dimension at setup time).
5. Writes `~/.memora/config.yaml`; prints "Next: `memora ingest --dry-run`".

Re-running `memora init` loads the existing config and edits it (add/remove sources) rather than starting over. A documented example config in the README is the wizard-free escape hatch.

## 4. Source Adapter Interface

`memora/sources/base.py`:

- `SourceDocument`: stable `doc_id`, `text`, `timestamp`, `source_type`, `metadata` (includes which signal produced the timestamp, for auditability).
- `Source` interface:
  - `discover() -> Iterator[SourceDocument]` — walk configured paths/globs.
  - `prompt_preamble: str` — short source-specific block prepended to the shared core prompt.
- **Timestamp resolution is adapter-owned**, fallback chain per adapter: source-native timestamps (chat exports carry them) → filename patterns (current diary convention keeps working) → markdown front-matter `date:` → file mtime. Principle preserved: temporal context comes from metadata, never inferred from content by the LLM.

Built-in adapters:

| Adapter | Files | Preamble concern |
|---|---|---|
| `markdown` | `.md`/`.txt` via globs | none beyond core (this is the certified path) |
| `conversation` | ChatGPT/Claude export JSON *and* plain-text call transcripts (format auto-detected: JSON → export structure, text → speaker-labeled transcript; transcript parsing reuses `voice/src/memory/call_extractor.py`) | two-party dialogue — extract only the USER's memories, never the assistant's/other speaker's |

Community contributors add a source by writing one file against this interface.

## 5. Prompts

`DIARY_EXTRACTION_PROMPT_V2` splits into:

- **Shared core** — memory types, exclusion rules, JSON schema. Byte-identical content to v2's substance; this is what the eval suite certifies (F1 0.926 with gpt-5.2).
- **Per-source preambles** — owned by each adapter, kept short.

`PROMPT_VERSIONS` remains so evals keep grading the core by version key. Certified-quality caveat goes in the README: numbers are for gpt-5.2; other backends vary — run the eval suite (`--backend`) to measure yours.

## 6. LLM Backend Layer

`memora/llm/base.py` defines one method: structured-JSON completion (prompt in, validated JSON out). Backends:

| Backend | Auth | Notes |
|---|---|---|
| `claude-subscription` (**default**) | Claude Code login | shells out to `claude -p --output-format json`; zero marginal cost on a subscription; requires CLI installed; slower than direct API; must guard against `ANTHROPIC_API_KEY` being set |
| `openai-compatible` | API key + base_url | OpenAI, DeepSeek, Ollama, OpenRouter, Groq |
| `anthropic` | `ANTHROPIC_API_KEY` | native SDK |
| `gemini` | `GEMINI_API_KEY` | native SDK |

Chat agent and extractor both go through this layer. Native `anthropic`/`gemini` backends are the last, lowest-risk implementation step. The eval runner gains `--backend` to measure any backend's extraction quality.

**Embeddings are a separate axis** (`embeddings:` config block): OpenAI-compatible endpoints only — Anthropic has no embeddings API and `claude -p` cannot embed. Default `text-embedding-3-small`; Ollama documented for fully-local.

## 7. Incremental Processing

`data/processed_diaries.txt` → state file in `~/.memora/state/` keyed by `doc_id` + content hash: unchanged files are skipped, edited files are re-extracted. `memora ingest` flags: `--dry-run`, `--source <name>`.

## 8. Error Handling

- Unreadable/unparseable file → skip with warning, count in the run summary; one bad file never kills a batch.
- Missing config → "run `memora init` first."
- `claude` CLI missing/logged-out (default backend) → clear message with install/login instructions, offer to switch backend.
- Neo4j unreachable → actionable message distinguishing "Docker container not running" from bad credentials.

## 9. Verification

- Unit tests: each adapter's discovery + timestamp fallback chain; config loader; backend selection.
- Eval suite stays green after the prompt split (core content unchanged → same F1 expected).
- End-to-end: `memora init` → `memora ingest --dry-run` → `memora ingest` → `memora mcp` on a sample directory.

## Build Order (within this project)

1. Config loader + schema (current tree)
2. Source adapter interface + markdown adapter (extractor consumes `SourceDocument`)
3. Prompt split: shared core + preambles; evals re-run, must match v2 numbers
4. conversation adapter (chat exports + call transcripts)
5. Incremental state file
6. LLM backend layer: interface + openai-compatible + claude-subscription (default)
7. anthropic + gemini backends; eval `--backend` flag
8. Package rename `src/` → `memora/`, pyproject.toml, CLI (`init` wizard, `ingest`, `chat`, `mcp`), delete `entrypoints/`
9. README rewrite for the new UX

Each step leaves evals green and is a separate commit.
