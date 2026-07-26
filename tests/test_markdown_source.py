from src.config import SourceConfig
from src.sources import build_source
from src.sources.markdown import MarkdownSource


def make(tmp_path, include=None):
    cfg = SourceConfig(
        name="j", type="markdown", paths=[str(tmp_path)],
        include=include or ["**/*.md", "**/*.txt"],
    )
    return build_source(cfg)


def test_build_source_returns_markdown_adapter(tmp_path):
    assert isinstance(make(tmp_path), MarkdownSource)


def test_discovers_files_and_reads_text(tmp_path):
    (tmp_path / "a.md").write_text("hello world")
    (tmp_path / "skip.pdf").write_text("nope")
    docs = list(make(tmp_path).discover())
    assert len(docs) == 1
    assert docs[0].text == "hello world"
    assert docs[0].source_type == "markdown"
    assert docs[0].doc_id.endswith("a.md")


def test_timestamp_from_diary_filename(tmp_path):
    f = tmp_path / "[34B84EC6-BCB1-4652-9EFA-6BC0D9B17698]-[2026-01-04-13-01-20].md"
    f.write_text("entry")
    (doc,) = make(tmp_path).discover()
    assert doc.timestamp == "2026-01-04T13:01:20"
    assert doc.metadata["timestamp_source"] == "filename"


def test_timestamp_from_frontmatter(tmp_path):
    (tmp_path / "note.md").write_text("---\ndate: 2025-03-01\n---\nbody text")
    (doc,) = make(tmp_path).discover()
    assert doc.timestamp == "2025-03-01T00:00:00"
    assert doc.metadata["timestamp_source"] == "frontmatter"
    assert doc.text == "body text"  # frontmatter stripped


def test_timestamp_falls_back_to_mtime(tmp_path):
    (tmp_path / "plain.md").write_text("no date anywhere")
    (doc,) = make(tmp_path).discover()
    assert doc.metadata["timestamp_source"] == "mtime"
    assert len(doc.timestamp) == 19  # ISO seconds precision
