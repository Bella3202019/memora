from src.config import SourceConfig
from src.sources.base import Source, SourceDocument
from src.sources.conversation import ConversationSource
from src.sources.markdown import MarkdownSource

_REGISTRY = {
    "markdown": MarkdownSource,
    "conversation": ConversationSource,
}


def build_source(cfg: SourceConfig) -> Source:
    try:
        return _REGISTRY[cfg.type](cfg)
    except KeyError:
        raise ValueError(f"Unknown source type: {cfg.type}")
