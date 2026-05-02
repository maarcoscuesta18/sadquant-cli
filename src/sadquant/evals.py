from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sadquant.models import EvalCase, EvalResult
from sadquant.rag import RagStore


def load_eval_cases(path: Path) -> list[EvalCase]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        try:
            cases.append(
                EvalCase(
                    ticker=str(payload["ticker"]).upper(),
                    horizon=str(payload.get("horizon", "all")),
                    question=str(payload["question"]),
                    expected_facts=[str(item) for item in payload.get("expected_facts", [])],
                    accepted_source_ids=[str(item) for item in payload.get("accepted_source_ids", [])],
                    required_claims=[str(item) for item in payload.get("required_claims", [])],
                    forbidden_claims=[str(item) for item in payload.get("forbidden_claims", [])],
                    labels={str(key): str(value) for key, value in payload.get("labels", {}).items()},
                )
            )
        except KeyError as exc:
            raise ValueError(f"{path}:{line_number} missing required field {exc}") from exc
    return cases


def run_rag_eval(
    cases: list[EvalCase],
    *,
    store: RagStore | None = None,
    limit: int = 8,
) -> tuple[list[EvalResult], dict[str, Any]]:
    store = store or RagStore()
    results = [_score_case(case, store=store, limit=limit) for case in cases]
    summary = summarize_eval_results(results)
    return results, summary


def summarize_eval_results(results: list[EvalResult]) -> dict[str, Any]:
    if not results:
        return {"case_count": 0}
    metrics = [
        "fact_accuracy",
        "citation_coverage",
        "unsupported_claim_rate",
        "recall_at_k",
        "mrr",
        "ndcg",
        "abstention_quality",
        "tool_error_rate",
    ]
    summary: dict[str, Any] = {"case_count": len(results)}
    for metric in metrics:
        summary[metric] = round(sum(getattr(result, metric) for result in results) / len(results), 4)
    return summary


def write_eval_report(path: Path, results: list[EvalResult], summary: dict[str, Any]) -> None:
    payload = {
        "summary": summary,
        "results": [asdict(result) for result in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _score_case(case: EvalCase, *, store: RagStore, limit: int) -> EvalResult:
    hits = store.hybrid_search(
        case.ticker,
        case.question,
        horizon=None if case.horizon == "all" else case.horizon,
        labels=case.labels,
        limit=limit,
    )
    retrieved_text = "\n".join(hit.chunk.contextual_text for hit in hits).lower()
    retrieved_source_ids = [hit.source_id for hit in hits]
    expected = [fact.lower() for fact in case.expected_facts]
    found = [fact for fact in expected if fact in retrieved_text]
    required = [claim.lower() for claim in case.required_claims]
    required_found = [claim for claim in required if claim in retrieved_text]
    forbidden = [claim.lower() for claim in case.forbidden_claims]
    forbidden_found = [claim for claim in forbidden if claim in retrieved_text]

    fact_accuracy = _ratio(len(found), len(expected))
    if required:
        fact_accuracy = (fact_accuracy + _ratio(len(required_found), len(required))) / 2
    citation_coverage = _citation_coverage(case.accepted_source_ids, retrieved_source_ids)
    unsupported_claim_rate = _ratio(len(forbidden_found), max(1, len(forbidden))) if forbidden else 0.0
    recall_at_k = _ratio(len(found), len(expected))
    mrr = _mrr(expected, hits)
    ndcg = _ndcg(expected, hits)
    abstention_quality = 1.0 if not expected and not hits else 0.0 if not expected else 1.0
    tool_error_rate = 0.0

    return EvalResult(
        ticker=case.ticker,
        horizon=case.horizon,
        question=case.question,
        fact_accuracy=round(fact_accuracy, 4),
        citation_coverage=round(citation_coverage, 4),
        unsupported_claim_rate=round(unsupported_claim_rate, 4),
        recall_at_k=round(recall_at_k, 4),
        mrr=round(mrr, 4),
        ndcg=round(ndcg, 4),
        abstention_quality=round(abstention_quality, 4),
        tool_error_rate=round(tool_error_rate, 4),
        retrieved_source_ids=retrieved_source_ids,
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return numerator / denominator


def _citation_coverage(accepted: list[str], retrieved: list[str]) -> float:
    if not accepted:
        return 1.0 if retrieved else 0.0
    accepted_set = set(accepted)
    retrieved_set = set(retrieved)
    return len(accepted_set & retrieved_set) / len(accepted_set)


def _mrr(expected: list[str], hits) -> float:
    if not expected:
        return 1.0
    for rank, hit in enumerate(hits, start=1):
        text = hit.chunk.contextual_text.lower()
        if any(fact in text for fact in expected):
            return 1.0 / rank
    return 0.0


def _ndcg(expected: list[str], hits) -> float:
    if not expected:
        return 1.0
    gains = []
    for hit in hits:
        text = hit.chunk.contextual_text.lower()
        gains.append(sum(1 for fact in expected if fact in text))
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    ideal_gains = sorted(gains, reverse=True)
    ideal_dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal_gains))
    if ideal_dcg == 0:
        return 0.0
    return dcg / ideal_dcg
