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
