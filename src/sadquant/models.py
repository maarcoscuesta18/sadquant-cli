from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class MarketSnapshot:
    ticker: str
    last_price: float
    change_20d_pct: float
    change_60d_pct: float
    rsi_14: float
    sma_20: float
    sma_50: float
    sma_200: Optional[float]
    volatility_20d: float
    high_52w: float
    low_52w: float
    observations: int


@dataclass(frozen=True)
class Signal:
    ticker: str
    label: str
    score: float
    confidence: float
    reasons: list[str]
    risks: list[str]


@dataclass(frozen=True)
class RiskSnapshot:
    ticker: str
    volatility_20d: float
    distance_from_52w_high_pct: float
    distance_from_52w_low_pct: float
    drawdown_from_high_pct: float
    risk_label: str
    notes: list[str]


@dataclass(frozen=True)
class FundamentalSnapshot:
    ticker: str
    source: str
    valuation: dict[str, Any]
    profitability: dict[str, Any]
    growth: dict[str, Any]
    ownership: dict[str, Any]
    notes: list[str]


@dataclass(frozen=True)
class SetupPlan:
    ticker: str
    horizon: str
    signal: Signal
    snapshot: MarketSnapshot
    risk: RiskSnapshot
    bias: str
    entry_zone: str
    invalidation: str
    targets: list[str]
    watch_items: list[str]
    data_gaps: list[str]


@dataclass(frozen=True)
class ScreenResult:
    ticker: str
    recipe: str
    score: float
    signal: str
    confidence: float
    price: float
    change_20d_pct: float
    change_60d_pct: float
    rsi_14: float
    volatility_20d: float
    reasons: list[str]


@dataclass(frozen=True)
class Watchlist:
    name: str
    tickers: list[str]
    updated_at: str


@dataclass(frozen=True)
class Thesis:
    id: int
    ticker: str
    horizon: str
    thesis: str
    evidence: str
    risks: str
    review_date: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ForwardReturnResult:
    signal_id: int
    ticker: str
    horizon: str
    created_at: str
    bias: str
    entry_price: float | None
    returns: dict[str, float | None]
    max_favorable_excursion_pct: float | None
    max_adverse_excursion_pct: float | None
    outcome: str


@dataclass(frozen=True)
class RagDocument:
    ticker: str
    source: str
    title: str
    body: str
    created_at: str


@dataclass(frozen=True)
class RagChunk:
    id: int
    doc_id: int
    ticker: str
    source: str
    title: str
    raw_text: str
    contextual_text: str
    created_at: str
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_id: str = ""


@dataclass(frozen=True)
class RetrievalHit:
    chunk: RagChunk
    method: str
    bm25_score: float
    vector_score: float
    fused_score: float
    source_id: str


@dataclass(frozen=True)
class ResearchClaim:
    text: str
    claim_type: str
    cited_source_ids: list[str]
    support_status: str


@dataclass(frozen=True)
class ResearchReport:
    ticker: str
    horizon: str
    bias: str
    score: float
    confidence: str
    claims: list[ResearchClaim]
    unsupported_claims: list[str]
    data_freshness: list[dict[str, str]]
    markdown: str


@dataclass(frozen=True)
class EvalCase:
    ticker: str
    horizon: str
    question: str
    expected_facts: list[str]
    accepted_source_ids: list[str] = field(default_factory=list)
    required_claims: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalResult:
    ticker: str
    horizon: str
    question: str
    fact_accuracy: float
    citation_coverage: float
    unsupported_claim_rate: float
    recall_at_k: float
    mrr: float
    ndcg: float
    abstention_quality: float
    tool_error_rate: float
    retrieved_source_ids: list[str]
