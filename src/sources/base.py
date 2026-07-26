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
