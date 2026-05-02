from datetime import datetime, timezone

from sadquant.evals import load_eval_cases, run_rag_eval
from sadquant.models import RagDocument
from sadquant.rag import RagStore


def test_rag_eval_scores_expected_fact_retrieval(tmp_path):
    store = RagStore(tmp_path / "rag.sqlite")
    store.add(
        RagDocument(
            ticker="AMD",
            source="manual",
            title="Margin note",
            body="AMD gross margin expanded to 52 percent while data center revenue accelerated.",
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
        labels={"horizon": "swing"},
    )
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        '{"ticker":"AMD","horizon":"swing","question":"What happened to margin?",'
        '"expected_facts":["gross margin expanded to 52 percent"],'
        '"required_claims":["data center revenue accelerated"]}\n',
        encoding="utf-8",
    )

    cases = load_eval_cases(dataset)
    results, summary = run_rag_eval(cases, store=store, limit=5)

    assert summary["case_count"] == 1
    assert results[0].fact_accuracy == 1.0
    assert results[0].recall_at_k == 1.0


def test_rag_eval_penalizes_forbidden_claims(tmp_path):
    store = RagStore(tmp_path / "rag.sqlite")
    store.add(
        RagDocument(
            ticker="TSLA",
            source="manual",
            title="Risk note",
            body="TSLA demand weakened and margins compressed.",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        '{"ticker":"TSLA","horizon":"swing","question":"What are risks?",'
        '"expected_facts":["demand weakened"],"forbidden_claims":["margins compressed"]}\n',
        encoding="utf-8",
    )

    results, _ = run_rag_eval(load_eval_cases(dataset), store=store, limit=5)

    assert results[0].unsupported_claim_rate == 1.0
