import asyncio
import json

from memora.config import Config, SourceConfig, LLMConfig, EmbeddingsConfig, Neo4jConfig
from memora.ingest import IngestState, ingest
from memora.llm.base import LLMBackend


class FakeBackend(LLMBackend):
    async def complete_json(self, system, user):
        return {"experiences": [], "emotions": [], "truths": [],
                "relationships": {}}


def make_config(tmp_path):
    return Config(
        user_id="t",
        sources=[SourceConfig(name="j", type="markdown",
                              paths=[str(tmp_path / "docs")])],
        llm=LLMConfig(), embeddings=EmbeddingsConfig(), neo4j=Neo4jConfig(),
    )


def test_state_roundtrip(tmp_path):
    state = IngestState(tmp_path / "state.json")
    assert not state.is_processed("a", "text")
    state.mark("a", "text")
    assert state.is_processed("a", "text")
    assert not state.is_processed("a", "EDITED text")  # content changed
    reloaded = IngestState(tmp_path / "state.json")
    assert reloaded.is_processed("a", "text")


def test_dry_run_extracts_without_marking(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("I hiked today with Sam.")
    cfg = make_config(tmp_path)
    state_path = tmp_path / "state.json"
    summary = asyncio.run(ingest(cfg, dry_run=True, state_path=state_path,
                                 backend=FakeBackend()))
    assert summary["processed"] == 1
    assert summary["errors"] == 0
    # dry run must not mark anything processed
    summary2 = asyncio.run(ingest(cfg, dry_run=True, state_path=state_path,
                                  backend=FakeBackend()))
    assert summary2["processed"] == 1


def test_unknown_source_name(tmp_path):
    cfg = make_config(tmp_path)
    (tmp_path / "docs").mkdir()
    summary = asyncio.run(ingest(cfg, source_name="nope", dry_run=True,
                                 state_path=tmp_path / "s.json",
                                 backend=FakeBackend()))
    assert summary["total"] == 0
