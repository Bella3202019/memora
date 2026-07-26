import json

from memora.config import SourceConfig
from memora.sources import build_source
from memora.sources.conversation import ConversationSource

CHATGPT_EXPORT = [{
    "title": "Trip planning",
    "create_time": 1751364000.0,  # 2025-07-01 UTC
    "mapping": {
        "n1": {"message": {"author": {"role": "user"},
                            "content": {"parts": ["I want to visit Kyoto"]}}},
        "n2": {"message": {"author": {"role": "assistant"},
                            "content": {"parts": ["Great choice!"]}}},
        "n3": {"message": None},
    },
}]

CLAUDE_EXPORT = [{
    "name": "Career chat",
    "created_at": "2025-06-15T10:30:00Z",
    "chat_messages": [
        {"sender": "human", "text": "I got promoted today"},
        {"sender": "assistant", "text": "Congratulations!"},
    ],
}]


def make(tmp_path, include):
    cfg = SourceConfig(name="c", type="conversation",
                       paths=[str(tmp_path)], include=include)
    return build_source(cfg)


def test_registered_in_factory(tmp_path):
    assert isinstance(make(tmp_path, ["**/*.json"]), ConversationSource)


def test_preamble_mentions_user_only(tmp_path):
    pre = ConversationSource.prompt_preamble
    assert "USER" in pre and "assistant" in pre.lower()


def test_chatgpt_export(tmp_path):
    (tmp_path / "conversations.json").write_text(json.dumps(CHATGPT_EXPORT))
    (doc,) = make(tmp_path, ["**/*.json"]).discover()
    assert doc.source_type == "conversation"
    assert "[User]: I want to visit Kyoto" in doc.text
    assert "[Assistant]: Great choice!" in doc.text
    assert doc.timestamp.startswith("2025-07-01")
    assert doc.metadata["timestamp_source"] == "native"
    assert doc.doc_id.endswith("conversations.json#0")


def test_claude_export(tmp_path):
    (tmp_path / "conversations.json").write_text(json.dumps(CLAUDE_EXPORT))
    (doc,) = make(tmp_path, ["**/*.json"]).discover()
    assert "[User]: I got promoted today" in doc.text
    assert doc.timestamp == "2025-06-15T10:30:00"


def test_plain_text_transcript(tmp_path):
    (tmp_path / "call.txt").write_text("User: hello\nAgent: hi there\n")
    (doc,) = make(tmp_path, ["**/*.txt"]).discover()
    assert "[User]: hello" in doc.text
    assert doc.metadata["timestamp_source"] == "mtime"


def test_unparseable_json_skipped(tmp_path):
    (tmp_path / "bad.json").write_text("{not json")
    assert list(make(tmp_path, ["**/*.json"]).discover()) == []
