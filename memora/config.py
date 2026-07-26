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
