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
    if backend == "openai-compatible":
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
