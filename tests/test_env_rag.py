from datetime import datetime, timezone

import sadquant.env as env
from sadquant.models import RagDocument
from sadquant.rag import RagStore, chunk_text, freshness_bucket


def test_load_dotenv_reads_cwd_file_without_overriding_existing_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXISTING_KEY", "shell")
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setattr(env, "_LOADED", False)
    (tmp_path / ".env").write_text('$env:FMP_API_KEY="from-file"\nEXISTING_KEY=file\n', encoding="utf-8")

    env.load_dotenv()

    assert env.os.getenv("FMP_API_KEY") == "from-file"
    assert env.os.getenv("EXISTING_KEY") == "shell"


def test_rag_search_sanitizes_punctuation_for_fts(tmp_path):
    store = RagStore(tmp_path / "rag.sqlite")
    store.add(
        RagDocument(
            ticker="AMD",
            source="manual",
            title="Setup",
            body="AMD long short dossier context",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )

    matches = store.search("AMD", "Build a full long/short dossier", limit=5)

    assert len(matches) == 1
    assert matches[0].ticker == "AMD"


def test_hybrid_search_uses_labels_and_contextual_chunks(tmp_path):
    store = RagStore(tmp_path / "rag.sqlite")
    created_at = datetime.now(timezone.utc).isoformat()
    store.add(
        RagDocument(
            ticker="NVDA",
            source="manual",
            title="Swing catalyst",
            body="NVDA management raised data center revenue guidance after Blackwell demand accelerated.",
            created_at=created_at,
        ),
        labels={"horizon": "swing", "event_type": "guidance"},
    )
    store.add(
        RagDocument(
            ticker="NVDA",
            source="manual",
            title="Position note",
            body="NVDA long duration thesis depends on data center capex durability.",
            created_at=created_at,
        ),
        labels={"horizon": "position", "event_type": "thesis"},
    )

    hits = store.hybrid_search("NVDA", "guidance demand", horizon="swing", limit=5)

    assert hits
    assert hits[0].chunk.labels["horizon"] == "swing"
    assert "document_type" in hits[0].chunk.contextual_text
    assert hits[0].source_id.startswith("NVDA:manual:")


def test_chunk_text_overlaps_long_documents():
    chunks = chunk_text(" ".join(["sentence."] * 500), max_chars=200, overlap=40)

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)


def test_freshness_bucket_marks_recent_dates():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)

    assert freshness_bucket("2026-01-09T00:00:00+00:00", now=now) == "fresh"
