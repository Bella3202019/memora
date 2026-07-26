from memora.config import SourceConfig
from memora.sources.base import Source, SourceDocument
from memora.sources.conversation import ConversationSource
from memora.sources.markdown import MarkdownSource

_REGISTRY = {
    "markdown": MarkdownSource,
    "conversation": ConversationSource,
}


def build_source(cfg: SourceConfig) -> Source:
    try:
        return _REGISTRY[cfg.type](cfg)
    except KeyError:
        raise ValueError(f"Unknown source type: {cfg.type}")
