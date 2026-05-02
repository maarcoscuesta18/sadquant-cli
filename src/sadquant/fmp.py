from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sadquant.market_data import MarketDataError, fetch_snapshots
from sadquant.providers import FmpProvider
from sadquant.rag import RagStore
from sadquant.models import RagDocument
from sadquant.signals import score_snapshot


FMP_MARKET_TTL = 5 * 60
FMP_CATALYST_TTL = 6 * 60 * 60
FMP_FINANCIAL_TTL = 24 * 60 * 60
FMP_TRANSCRIPT_TTL = 30 * 24 * 60 * 60


def fmp_market_context(ticker: str, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    quote = _first(provider.get("quote", {"symbol": symbol}, cache_ttl=FMP_MARKET_TTL))
    price_change = provider.get("stock-price-change", {"symbol": symbol}, cache_ttl=FMP_MARKET_TTL)
    history = provider.get(
        "historical-price-eod/full",
        {"symbol": symbol},
        cache_ttl=FMP_MARKET_TTL,
    )
    rsi = provider.get(
        "technical-indicators/rsi",
        {"symbol": symbol, "periodLength": 14, "timeframe": "1day"},
        cache_ttl=FMP_MARKET_TTL,
    )
    return {
        "ticker": symbol,
        "quote": _pick(
            quote,
            [
                "symbol",
                "name",
                "price",
                "change",
                "changesPercentage",
                "volume",
                "avgVolume",
                "dayLow",
                "dayHigh",
                "yearLow",
                "yearHigh",
                "marketCap",
                "exchange",
                "timestamp",
            ],
        ),
        "price_change": price_change,
        "history_tail": _limit_rows(_extract_historical_rows(history), 8),
        "rsi_tail": _limit_rows(_as_list(rsi), 5),
    }


def fmp_fundamentals_context(ticker: str, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    return {
        "ticker": symbol,
        "profile": _first(provider.get("profile", {"symbol": symbol}, cache_ttl=FMP_FINANCIAL_TTL)),
        "peers": provider.get("stock-peers", {"symbol": symbol}, cache_ttl=FMP_FINANCIAL_TTL),
        "income_statement": _limit_rows(
            _as_list(provider.get("income-statement", {"symbol": symbol, "period": "annual", "limit": 4}, cache_ttl=FMP_FINANCIAL_TTL)),
            4,
        ),
        "balance_sheet": _limit_rows(
            _as_list(provider.get("balance-sheet-statement", {"symbol": symbol, "period": "annual", "limit": 4}, cache_ttl=FMP_FINANCIAL_TTL)),
            4,
        ),
        "cash_flow": _limit_rows(
            _as_list(provider.get("cash-flow-statement", {"symbol": symbol, "period": "annual", "limit": 4}, cache_ttl=FMP_FINANCIAL_TTL)),
            4,
        ),
        "key_metrics": _limit_rows(
            _as_list(provider.get("key-metrics", {"symbol": symbol, "period": "annual", "limit": 4}, cache_ttl=FMP_FINANCIAL_TTL)),
            4,
        ),
        "key_metrics_ttm": _first(provider.get("key-metrics-ttm", {"symbol": symbol}, cache_ttl=FMP_FINANCIAL_TTL)),
    }


def fmp_estimates_context(ticker: str, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    return {
        "ticker": symbol,
        "analyst_estimates": _limit_rows(
            _as_list(
                provider.get(
                    "analyst-estimates",
                    {"symbol": symbol, "period": "annual", "page": 0, "limit": 6},
                    cache_ttl=FMP_FINANCIAL_TTL,
                )
            ),
            6,
        ),
        "ratings_snapshot": _first(provider.get("ratings-snapshot", {"symbol": symbol}, cache_ttl=FMP_FINANCIAL_TTL)),
        "price_target_consensus": _first(provider.get("price-target-consensus", {"symbol": symbol}, cache_ttl=FMP_FINANCIAL_TTL)),
    }


def fmp_catalysts_context(ticker: str, limit: int = 10, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    return {
        "ticker": symbol,
        "news": _normalize_articles(
            provider.get("news/stock", {"symbols": symbol, "page": 0, "limit": limit}, cache_ttl=FMP_CATALYST_TTL),
            limit=limit,
        ),
        "press_releases": _normalize_articles(
            provider.get("news/press-releases", {"symbols": symbol, "page": 0, "limit": limit}, cache_ttl=FMP_CATALYST_TTL),
            limit=limit,
        ),
    }


def fmp_transcripts_context(ticker: str, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    latest = provider.get(
        "earning-call-transcript-latest",
        {"symbol": symbol, "limit": 10},
        cache_ttl=FMP_TRANSCRIPT_TTL,
    )
    candidate = _find_transcript_candidate(symbol, latest)
    transcript: Any = None
    if candidate:
        year = candidate.get("year") or _year_from_date(candidate.get("date"))
        quarter = candidate.get("quarter") or candidate.get("period")
        if year and quarter:
            transcript = provider.get(
                "earning-call-transcript",
                {"symbol": symbol, "year": year, "quarter": quarter},
                cache_ttl=FMP_TRANSCRIPT_TTL,
            )

    return {
        "ticker": symbol,
        "latest_metadata": _limit_rows(_as_list(latest), 5),
        "selected_transcript": _normalize_transcript(transcript),
    }


def fmp_insiders_context(ticker: str, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    return {
        "ticker": symbol,
        "statistics": _limit_rows(
            _as_list(provider.get("insider-trading/statistics", {"symbol": symbol}, cache_ttl=FMP_FINANCIAL_TTL)),
            12,
        )
    }


def fmp_signal_context(ticker: str, provider: Optional[FmpProvider] = None) -> dict[str, Any]:
    provider = provider or FmpProvider()
    symbol = ticker.upper()
    score = 0.0
    reasons: list[str] = []
    risks: list[str] = []

    try:
        snapshots = fetch_snapshots([symbol], period="1y")
    except MarketDataError as exc:
        snapshots = []
        risks.append(f"Yahoo technical snapshot unavailable: {exc}")

    if snapshots:
        signal = score_snapshot(snapshots[0])
        score += signal.score
        reasons.extend(signal.reasons)
        risks.extend(signal.risks)

    fundamentals = fmp_fundamentals_context(symbol, provider)
    metrics_ttm = fundamentals.get("key_metrics_ttm") or {}
    score += _quality_score(metrics_ttm, reasons, risks)

    estimates = fmp_estimates_context(symbol, provider)
    quote = _first(provider.get("quote", {"symbol": symbol}, cache_ttl=FMP_MARKET_TTL))
    score += _analyst_score(quote, estimates.get("price_target_consensus") or {}, reasons, risks)

    catalysts = fmp_catalysts_context(symbol, limit=10, provider=provider)
    catalyst_count = len(catalysts.get("news", [])) + len(catalysts.get("press_releases", []))
    if catalyst_count >= 5:
        score += 0.25
        reasons.append(f"FMP returned {catalyst_count} recent catalyst item(s).")

    insiders = fmp_insiders_context(symbol, provider)
    score += _insider_score(insiders.get("statistics", []), reasons, risks)

    if score >= 2.0:
        label = "LONG_BIAS"
    elif score <= -2.0:
        label = "SHORT_BIAS"
    else:
        label = "NEUTRAL"

    return {
        "ticker": symbol,
        "signal": label,
        "score": round(score, 2),
        "confidence": round(min(0.95, max(0.15, abs(score) / 6)), 2),
        "components": {
            "technical": "existing yfinance signal when available",
            "quality": "FMP key metrics TTM",
            "analyst": "FMP price target consensus versus latest quote",
            "catalysts": "FMP news and press release count",
            "insiders": "FMP insider trading statistics",
        },
        "reasons": reasons or ["No strong combined FMP/yfinance signal edge detected."],
        "risks": risks,
    }


def ingest_fmp_context(
    ticker: str,
    *,
    include_news: bool,
    include_press_releases: bool,
    include_transcripts: bool,
    limit: int,
    contextualize: bool = True,
    provider: Optional[FmpProvider] = None,
    store: Optional[RagStore] = None,
) -> int:
    provider = provider or FmpProvider()
    store = store or RagStore()
    symbol = ticker.upper()
    documents: list[RagDocument] = []
    now = datetime.now(timezone.utc).isoformat()

    if include_news:
        catalysts = fmp_catalysts_context(symbol, limit=limit, provider=provider)
        documents.extend(_article_documents(symbol, "news", catalysts.get("news", []), now))

    if include_press_releases:
        catalysts = fmp_catalysts_context(symbol, limit=limit, provider=provider)
        documents.extend(_article_documents(symbol, "press_release", catalysts.get("press_releases", []), now))

    if include_transcripts:
        transcript_context = fmp_transcripts_context(symbol, provider)
        transcript = transcript_context.get("selected_transcript")
        if transcript:
            documents.extend(_transcript_documents(symbol, transcript, now))

    for doc in documents:
        store.add(doc, contextualize=contextualize)
    return len(documents)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("historical", "data", "results"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    return [value]


def _first(value: Any) -> dict[str, Any]:
    rows = _as_list(value)
    first = rows[0] if rows else {}
    return first if isinstance(first, dict) else {}


def _pick(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: row.get(key) for key in keys if key in row}


def _limit_rows(rows: list[Any], limit: int) -> list[Any]:
    return rows[:limit]


def _extract_historical_rows(value: Any) -> list[Any]:
    if isinstance(value, dict) and isinstance(value.get("historical"), list):
        return value["historical"]
    return _as_list(value)


def _normalize_articles(value: Any, limit: int) -> list[dict[str, Any]]:
    articles = []
    for row in _limit_rows(_as_list(value), limit):
        if not isinstance(row, dict):
            continue
        articles.append(
            {
                "published_date": row.get("publishedDate") or row.get("date"),
                "title": row.get("title"),
                "site": row.get("site") or row.get("publisher"),
                "url": row.get("url"),
                "text": _truncate(row.get("text") or row.get("summary") or row.get("content") or "", 900),
            }
        )
    return articles


def _find_transcript_candidate(symbol: str, latest: Any) -> Optional[dict[str, Any]]:
    for row in _as_list(latest):
        if not isinstance(row, dict):
            continue
        row_symbol = str(row.get("symbol") or row.get("ticker") or "").upper()
        if row_symbol == symbol:
            return row
    rows = [row for row in _as_list(latest) if isinstance(row, dict)]
    return rows[0] if rows else None


def _year_from_date(value: Any) -> Optional[int]:
    if not value:
        return None
    text = str(value)
    try:
        return int(text[:4])
    except ValueError:
        return None


def _normalize_transcript(value: Any) -> Optional[dict[str, Any]]:
    row = _first(value)
    if not row:
        return None
    content = row.get("content") or row.get("transcript") or row.get("text") or ""
    return {
        "symbol": row.get("symbol"),
        "date": row.get("date"),
        "quarter": row.get("quarter"),
        "year": row.get("year"),
        "content": _truncate(content, 5000),
    }


def _quality_score(metrics: dict[str, Any], reasons: list[str], risks: list[str]) -> float:
    score = 0.0
    roic = _number(metrics.get("returnOnInvestedCapitalTTM") or metrics.get("roicTTM"))
    fcf_yield = _number(metrics.get("freeCashFlowYieldTTM"))
    pe = _number(metrics.get("peRatioTTM") or metrics.get("priceEarningsRatioTTM"))

    if roic is not None and roic > 0.12:
        score += 0.75
        reasons.append(f"FMP TTM ROIC is strong at {roic:.2f}.")
    elif roic is not None and roic < 0:
        score -= 0.75
        risks.append(f"FMP TTM ROIC is negative at {roic:.2f}.")

    if fcf_yield is not None and fcf_yield > 0.04:
        score += 0.5
        reasons.append(f"FMP free cash flow yield is supportive at {fcf_yield:.2f}.")
    elif fcf_yield is not None and fcf_yield < 0:
        score -= 0.5
        risks.append(f"FMP free cash flow yield is negative at {fcf_yield:.2f}.")

    if pe is not None and pe > 60:
        score -= 0.5
        risks.append(f"FMP TTM P/E is elevated at {pe:.1f}.")
    return score


def _analyst_score(quote: dict[str, Any], consensus: dict[str, Any], reasons: list[str], risks: list[str]) -> float:
    price = _number(quote.get("price"))
    target = _number(
        consensus.get("targetConsensus")
        or consensus.get("priceTargetConsensus")
        or consensus.get("targetMedian")
        or consensus.get("target")
    )
    if price is None or target is None or price <= 0:
        return 0.0
    upside = (target / price) - 1
    if upside > 0.15:
        reasons.append(f"FMP consensus target implies {upside:.1%} upside.")
        return 0.5
    if upside < -0.10:
        risks.append(f"FMP consensus target implies {abs(upside):.1%} downside.")
        return -0.5
    return 0.0


def _insider_score(statistics: list[Any], reasons: list[str], risks: list[str]) -> float:
    total = 0.0
    for row in statistics:
        if not isinstance(row, dict):
            continue
        acquisitions = _number(row.get("acquiredTransactions") or row.get("acquisitionTransactions"))
        dispositions = _number(row.get("disposedTransactions") or row.get("dispositionTransactions"))
        if acquisitions is not None:
            total += acquisitions
        if dispositions is not None:
            total -= dispositions
    if total > 0:
        reasons.append("FMP insider statistics skew toward acquisitions.")
        return 0.25
    if total < 0:
        risks.append("FMP insider statistics skew toward dispositions.")
        return -0.25
    return 0.0


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _article_documents(ticker: str, kind: str, articles: list[dict[str, Any]], now: str) -> list[RagDocument]:
    docs = []
    for article in articles:
        title = str(article.get("title") or f"FMP {kind}").strip()
        body = "\n".join(
            part
            for part in [
                str(article.get("published_date") or "").strip(),
                str(article.get("url") or "").strip(),
                str(article.get("text") or "").strip(),
            ]
            if part
        )
        if body:
            docs.append(RagDocument(ticker=ticker, source=f"fmp:{kind}", title=title, body=body, created_at=now))
    return docs


def _transcript_documents(ticker: str, transcript: dict[str, Any], now: str) -> list[RagDocument]:
    content = str(transcript.get("content") or "").strip()
    if not content:
        return []
    title = f"FMP earnings transcript {transcript.get('year') or ''} Q{transcript.get('quarter') or ''}".strip()
    chunks = [content[index : index + 3500] for index in range(0, len(content), 3500)]
    return [
        RagDocument(
            ticker=ticker,
            source="fmp:transcript",
            title=f"{title} part {position + 1}",
            body=chunk,
            created_at=now,
        )
        for position, chunk in enumerate(chunks)
    ]
