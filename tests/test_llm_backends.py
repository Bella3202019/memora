import pytest

from memora.config import LLMConfig
from memora.llm import get_backend
from memora.llm.base import extract_json_block
from memora.llm.openai_compat import OpenAICompatBackend
from memora.llm.claude_cli import ClaudeCLIBackend
from memora.llm.anthropic_api import AnthropicBackend
from memora.llm.gemini_api import GeminiBackend


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


def test_factory_anthropic():
    b = get_backend(LLMConfig(backend="anthropic", model="claude-sonnet-5"))
    assert isinstance(b, AnthropicBackend)
    assert b.model == "claude-sonnet-5"


def test_factory_gemini_default_model():
    b = get_backend(LLMConfig(backend="gemini"))
    assert isinstance(b, GeminiBackend)
    assert b.model == "gemini-2.5-flash"
