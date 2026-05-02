from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from sadquant.finviz import FinvizError, fetch_finviz_financials, fetch_finviz_snapshot
from sadquant.fmp import (
    fmp_catalysts_context,
    fmp_estimates_context,
    fmp_fundamentals_context,
    fmp_insiders_context,
    fmp_market_context,
    fmp_signal_context,
    fmp_transcripts_context,
)
from sadquant.insiders import fetch_insider_activity
from sadquant.market_data import MarketDataError, fetch_snapshots
from sadquant.providers import AdanosProvider, FmpProvider, FundaProvider
from sadquant.rag import RagStore
from sadquant.signals import score_snapshot
from sadquant.yahoo import fetch_yahoo_research


@dataclass(frozen=True)
class ToolResult:
    name: str
    data: dict[str, Any]
    source: str

    def to_prompt_block(self) -> str:
        return f"## Tool: {self.name}\nSource: {self.source}\nData: {self.data}\n"


ToolFn = Callable[[str, str], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, tool: ToolFn) -> None:
        self._tools[name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def run(self, name: str, ticker: str, query: str) -> ToolResult:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](ticker, query)


def market_snapshot_tool(ticker: str, query: str) -> ToolResult:
    snapshots = fetch_snapshots([ticker.upper()], period="1y")
    if not snapshots:
        raise MarketDataError(f"No usable market data for {ticker}.")
    snapshot = snapshots[0]
    signal = score_snapshot(snapshot)
    return ToolResult(
        name="market_snapshot",
        source="yfinance",
        data={
            "ticker": snapshot.ticker,
            "last_price": round(snapshot.last_price, 2),
            "change_20d_pct": round(snapshot.change_20d_pct, 2),
            "change_60d_pct": round(snapshot.change_60d_pct, 2),
            "rsi_14": round(snapshot.rsi_14, 2),
            "volatility_20d": round(snapshot.volatility_20d, 2),
            "signal": signal.label,
            "score": signal.score,
            "confidence": signal.confidence,
            "reasons": signal.reasons,
            "risks": signal.risks,
        },
    )


def yahoo_research_tool(ticker: str, query: str) -> ToolResult:
    return ToolResult(name="yahoo_research", source="yfinance", data=fetch_yahoo_research(ticker))


def local_rag_tool(ticker: str, query: str) -> ToolResult:
    docs = RagStore().search(ticker, query, limit=5)
    return ToolResult(
        name="local_rag",
        source="sqlite-fts5",
        data={
            "matches": [
                {
                    "ticker": doc.ticker,
                    "source": doc.source,
                    "title": doc.title,
                    "body": doc.body[:800],
                    "created_at": doc.created_at,
                }
                for doc in docs
            ]
        },
    )


def hybrid_rag_tool(ticker: str, query: str) -> ToolResult:
    hits = RagStore().hybrid_search(ticker, query, limit=8)
    return ToolResult(
        name="hybrid_rag",
        source="sqlite-hybrid-bm25-vector",
        data={
            "matches": [
                {
                    "source_id": hit.source_id,
                    "ticker": hit.chunk.ticker,
                    "source": hit.chunk.source,
                    "title": hit.chunk.title,
                    "created_at": hit.chunk.created_at,
                    "labels": hit.chunk.labels,
                    "method": hit.method,
                    "bm25_score": hit.bm25_score,
                    "vector_score": hit.vector_score,
                    "fused_score": hit.fused_score,
                    "contextual_text": hit.chunk.contextual_text[:1200],
                }
                for hit in hits
            ]
        },
    )


def web_search_tool(ticker: str, query: str) -> ToolResult:
    search_query = f"{ticker.upper()} stock {query}".strip()
    if os.getenv("TAVILY_API_KEY"):
        return _tavily_search(search_query)
    if os.getenv("BRAVE_SEARCH_API_KEY"):
        return _brave_search(search_query)
    return ToolResult(
        name="web_search",
        source="not-configured",
        data={
            "error": "Set TAVILY_API_KEY or BRAVE_SEARCH_API_KEY to enable live web search.",
            "query": search_query,
        },
    )


def sentiment_tool(ticker: str, query: str) -> ToolResult:
    provider = AdanosProvider()
    if not provider.available():
        return ToolResult(
            name="sentiment",
            source="not-configured",
            data={"error": "Set ADANOS_API_KEY to enable structured sentiment."},
        )
    payload = provider.sentiment_compare("news", [ticker.upper()], days=7)
    return ToolResult(name="sentiment", source="adanos-news", data=payload)


def funda_news_tool(ticker: str, query: str) -> ToolResult:
    provider = FundaProvider()
    if not provider.available():
        return ToolResult(
            name="funda_news",
            source="not-configured",
            data={"error": "Set FUNDA_API_KEY to enable Funda news/fundamentals."},
        )
    payload = provider.get("news", {"type": "stock", "ticker": ticker.upper()})
    return ToolResult(name="funda_news", source="funda", data=payload)


def finviz_snapshot_tool(ticker: str, query: str) -> ToolResult:
    try:
        payload = fetch_finviz_snapshot(ticker)
    except FinvizError as exc:
        return ToolResult(
            name="finviz_snapshot",
            source="finviz-unavailable",
            data={
                "ticker": ticker.upper(),
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
    return ToolResult(name="finviz_snapshot", source="finviz", data=payload)


def finviz_financials_tool(ticker: str, query: str) -> ToolResult:
    try:
        payload = fetch_finviz_financials(ticker)
    except FinvizError as exc:
        return ToolResult(
            name="finviz_financials",
            source="finviz-unavailable",
            data={
                "ticker": ticker.upper(),
                "error": str(exc),
                "error_type": type(exc).__name__,
                "periods": [],
                "rows": {},
                "summary": {"bias": "unavailable"},
            },
        )
    return ToolResult(name="finviz_financials", source="finviz", data=payload)


def insider_activity_tool(ticker: str, query: str) -> ToolResult:
    activity = fetch_insider_activity(ticker)
    return ToolResult(
        name="insider_activity",
        source="yfinance",
        data={
            "summary": activity.summary,
            "recent_transactions": activity.recent_transactions,
            "net_purchase_activity": activity.net_purchase_activity,
            "roster": activity.roster,
        },
    )


def fmp_market_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_market")
    return ToolResult(name="fmp_market", source="fmp", data=fmp_market_context(ticker, provider))


def fmp_fundamentals_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_fundamentals")
    return ToolResult(name="fmp_fundamentals", source="fmp", data=fmp_fundamentals_context(ticker, provider))


def fmp_estimates_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_estimates")
    return ToolResult(name="fmp_estimates", source="fmp", data=fmp_estimates_context(ticker, provider))


def fmp_catalysts_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_catalysts")
    return ToolResult(name="fmp_catalysts", source="fmp", data=fmp_catalysts_context(ticker, provider=provider))


def fmp_transcripts_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_transcripts")
    return ToolResult(name="fmp_transcripts", source="fmp", data=fmp_transcripts_context(ticker, provider))


def fmp_insiders_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_insiders")
    return ToolResult(name="fmp_insiders", source="fmp", data=fmp_insiders_context(ticker, provider))


def fmp_signal_context_tool(ticker: str, query: str) -> ToolResult:
    provider = FmpProvider()
    if not provider.available():
        return _fmp_not_configured("fmp_signal_context")
    return ToolResult(name="fmp_signal_context", source="fmp+yfinance", data=fmp_signal_context(ticker, provider))


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("market_snapshot", market_snapshot_tool)
    registry.register("yahoo_research", yahoo_research_tool)
    registry.register("local_rag", local_rag_tool)
    registry.register("hybrid_rag", hybrid_rag_tool)
    registry.register("web_search", web_search_tool)
    registry.register("sentiment", sentiment_tool)
    registry.register("funda_news", funda_news_tool)
    registry.register("finviz_snapshot", finviz_snapshot_tool)
    registry.register("finviz_financials", finviz_financials_tool)
    registry.register("insider_activity", insider_activity_tool)
    registry.register("fmp_market", fmp_market_tool)
    registry.register("fmp_fundamentals", fmp_fundamentals_tool)
    registry.register("fmp_estimates", fmp_estimates_tool)
    registry.register("fmp_catalysts", fmp_catalysts_tool)
    registry.register("fmp_transcripts", fmp_transcripts_tool)
    registry.register("fmp_insiders", fmp_insiders_tool)
    registry.register("fmp_signal_context", fmp_signal_context_tool)
    return registry


def _fmp_not_configured(name: str) -> ToolResult:
    return ToolResult(
        name=name,
        source="not-configured",
        data={"error": "Set FMP_API_KEY to enable Financial Modeling Prep deep research."},
    )


def _tavily_search(query: str) -> ToolResult:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": os.environ["TAVILY_API_KEY"],
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
            },
        )
        response.raise_for_status()
        payload = response.json()
    return ToolResult(name="web_search", source="tavily", data=payload)


def _brave_search(query: str) -> ToolResult:
    with httpx.Client(timeout=20) as client:
        response = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"X-Subscription-Token": os.environ["BRAVE_SEARCH_API_KEY"]},
        )
        response.raise_for_status()
        payload = response.json()
    return ToolResult(name="web_search", source="brave", data=payload)
