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
        "",                # include glob default for conversation
        "chats",           # name
        "n",               # add another?
        "", "", "1", "",   # neo4j x2, backend, embeddings
    ]
    rc = run_wizard(config_path, input_fn=scripted(answers),
                    print_fn=lambda *a, **k: None,
                    which_fn=lambda _: None)
    assert rc == 0
    cfg = yaml.safe_load(config_path.read_text())
    assert [s["name"] for s in cfg["sources"]] == ["old", "chats"]
