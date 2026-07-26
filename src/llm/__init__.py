from src.config import LLMConfig
from src.llm.anthropic_api import AnthropicBackend
from src.llm.base import LLMBackend
from src.llm.claude_cli import ClaudeCLIBackend
from src.llm.gemini_api import GeminiBackend
from src.llm.openai_compat import OpenAICompatBackend


def get_backend(cfg: LLMConfig) -> LLMBackend:
    if cfg.backend == "claude-subscription":
        return ClaudeCLIBackend(model=cfg.model)
    if cfg.backend == "openai-compatible":
        return OpenAICompatBackend(
            base_url=cfg.base_url, model=cfg.model or "gpt-5.2"
        )
    if cfg.backend == "anthropic":
        return AnthropicBackend(model=cfg.model or "claude-sonnet-5")
    if cfg.backend == "gemini":
        return GeminiBackend(model=cfg.model or "gemini-2.5-flash")
    raise ValueError(f"Unknown llm backend: {cfg.backend!r}")
