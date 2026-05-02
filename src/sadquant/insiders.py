from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from sadquant.market_data import MarketDataError


class InsiderDataError(MarketDataError):
    pass


@dataclass(frozen=True)
class InsiderActivity:
    ticker: str
    summary: dict[str, Any]
    recent_transactions: list[dict[str, Any]]
    net_purchase_activity: list[dict[str, Any]]
    roster: list[dict[str, Any]]


def fetch_insider_activity(ticker: str, limit: int = 12) -> InsiderActivity:
    """Fetch and normalize Yahoo Finance insider activity for one ticker."""
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise InsiderDataError("Missing dependency `yfinance`. Install with `python -m pip install -e .` first.") from exc

    symbol = ticker.upper()
    try:
        yahoo_ticker = yf.Ticker(symbol)
        transactions = yahoo_ticker.get_insider_transactions()
        purchases = yahoo_ticker.get_insider_purchases()
        roster = yahoo_ticker.get_insider_roster_holders()
    except Exception as exc:
        raise InsiderDataError(f"Could not fetch insider activity for {symbol}: {exc}") from exc

    recent_transactions = _records(transactions, limit=limit, date_columns=["Start Date"])
    net_purchase_activity = _records(purchases)
    insider_roster = _records(roster, limit=limit, date_columns=["Latest Transaction Date", "Position Direct Date", "Position Indirect Date"])

    return InsiderActivity(
        ticker=symbol,
        summary=_summarize(symbol, recent_transactions, net_purchase_activity),
        recent_transactions=recent_transactions,
        net_purchase_activity=net_purchase_activity,
        roster=insider_roster,
    )


def _records(
    frame: Any,
    limit: int | None = None,
    date_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return []

    clean = frame.copy()
    if limit is not None:
        clean = clean.head(limit)

    date_columns = date_columns or []
    for column in date_columns:
        if column in clean:
            clean[column] = pd.to_datetime(clean[column], errors="coerce").dt.date.astype("string")

    records: list[dict[str, Any]] = []
    for row in clean.replace({pd.NA: None}).to_dict(orient="records"):
        records.append({key: _scalar(value) for key, value in row.items() if _scalar(value) is not None})
    return records


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            return value
    return value


def _summarize(
    ticker: str,
    transactions: list[dict[str, Any]],
    net_activity: list[dict[str, Any]],
) -> dict[str, Any]:
    buys = _find_activity(net_activity, "Purchases")
    sales = _find_activity(net_activity, "Sales")
    net = _find_activity(net_activity, "Net Shares Purchased (Sold)")

    buy_shares = _number(buys.get("Shares"))
    sell_shares = _number(sales.get("Shares"))
    net_shares = _number(net.get("Shares"))
    buy_count = _number(buys.get("Trans"))
    sell_count = _number(sales.get("Trans"))
    net_count = _number(net.get("Trans"))

    if net_shares > 0:
        bias = "net_buying"
    elif net_shares < 0:
        bias = "net_selling"
    elif buy_shares > sell_shares:
        bias = "more_buying_than_selling"
    elif sell_shares > buy_shares:
        bias = "more_selling_than_buying"
    else:
        bias = "mixed_or_unavailable"

    return {
        "ticker": ticker,
        "bias": bias,
        "buy_shares": buy_shares,
        "sell_shares": sell_shares,
        "net_shares": net_shares,
        "buy_transactions": buy_count,
        "sell_transactions": sell_count,
        "net_transactions": net_count,
        "recent_transaction_count": len(transactions),
    }


def _find_activity(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    for row in rows:
        if any(str(value).lower() == label.lower() for value in row.values()):
            return row
    return {}


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except ValueError:
        return 0.0
