from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from sadquant.finviz import FinvizError, fetch_finviz_financials, fetch_finviz_snapshot
from sadquant.market_data import MarketDataError, build_snapshot, close_prices, fetch_history, fetch_snapshots
from sadquant.models import (
    ForwardReturnResult,
    FundamentalSnapshot,
    MarketSnapshot,
    RiskSnapshot,
    ScreenResult,
    SetupPlan,
)
from sadquant.signals import score_snapshot

SCREEN_RECIPES = {"momentum", "relative-strength", "vcp", "earnings-gap", "quality-growth", "value-dividend"}


def risk_snapshot(snapshot: MarketSnapshot) -> RiskSnapshot:
    high_gap = _pct_distance(snapshot.last_price, snapshot.high_52w)
    low_gap = _pct_distance(snapshot.last_price, snapshot.low_52w)
    drawdown = _pct_distance(snapshot.last_price, snapshot.high_52w)
    notes: list[str] = []
    if snapshot.volatility_20d >= 55:
        label = "high"
        notes.append("Realized volatility is high for a position-style setup.")
    elif snapshot.volatility_20d >= 35:
        label = "moderate"
        notes.append("Realized volatility is elevated; position size and invalidation matter.")
    else:
        label = "normal"
        notes.append("Realized volatility is not unusually elevated.")
    if high_gap <= -20:
        notes.append("Price is more than 20% below its 52-week high.")
    if low_gap >= 50:
        notes.append("Price is far above its 52-week low; avoid assuming low-risk entry.")
    return RiskSnapshot(
        ticker=snapshot.ticker,
        volatility_20d=round(snapshot.volatility_20d, 2),
        distance_from_52w_high_pct=round(high_gap, 2),
        distance_from_52w_low_pct=round(low_gap, 2),
        drawdown_from_high_pct=round(drawdown, 2),
        risk_label=label,
        notes=notes,
    )


def build_setup_plan(ticker: str, *, horizon: str = "swing", period: str = "1y") -> SetupPlan:
    snapshots = fetch_snapshots([ticker.upper()], period=period)
    if not snapshots:
        raise MarketDataError(f"No usable market snapshot for {ticker}.")
    snapshot = snapshots[0]
    signal = score_snapshot(snapshot)
    risk = risk_snapshot(snapshot)
    entry_zone = _entry_zone(snapshot, horizon)
    invalidation = _invalidation(snapshot, horizon)
    targets = _targets(snapshot, horizon)
    watch_items = _watch_items(snapshot, horizon, signal.label)
    gaps = []
    if snapshot.sma_200 is None:
        gaps.append("200-day moving average unavailable for this lookback.")
    if snapshot.observations < 200:
        gaps.append("Less than 200 observations; long-term trend confidence is reduced.")
    return SetupPlan(
        ticker=snapshot.ticker,
        horizon=horizon,
        signal=signal,
        snapshot=snapshot,
        risk=risk,
        bias=signal.label,
        entry_zone=entry_zone,
        invalidation=invalidation,
        targets=targets,
        watch_items=watch_items,
        data_gaps=gaps,
    )


def screen_snapshots(snapshots: list[MarketSnapshot], *, recipe: str) -> list[ScreenResult]:
    normalized = recipe.lower().strip()
    if normalized not in SCREEN_RECIPES:
        valid = ", ".join(sorted(SCREEN_RECIPES))
        raise ValueError(f"Unknown screen recipe '{recipe}'. Valid recipes: {valid}")
    results = [_screen_snapshot(snapshot, normalized) for snapshot in snapshots]
    return sorted(results, key=lambda result: result.score, reverse=True)


def compare_snapshots(snapshots: list[MarketSnapshot]) -> list[dict[str, Any]]:
    rows = []
    for snapshot in snapshots:
        signal = score_snapshot(snapshot)
        risk = risk_snapshot(snapshot)
        rows.append(
            {
                "ticker": snapshot.ticker,
                "signal": signal.label,
                "score": signal.score,
                "confidence": signal.confidence,
                "price": round(snapshot.last_price, 2),
                "change_20d_pct": round(snapshot.change_20d_pct, 2),
                "change_60d_pct": round(snapshot.change_60d_pct, 2),
                "rsi_14": round(snapshot.rsi_14, 2),
                "volatility_20d": round(snapshot.volatility_20d, 2),
                "risk": risk.risk_label,
                "distance_from_52w_high_pct": risk.distance_from_52w_high_pct,
            }
        )
    return rows


def fetch_fundamental_snapshot(ticker: str) -> FundamentalSnapshot:
    symbol = ticker.upper()
    notes: list[str] = []
    try:
        snapshot = fetch_finviz_snapshot(symbol)
    except FinvizError as exc:
        snapshot = {}
        notes.append(f"Finviz snapshot unavailable: {exc}")
    try:
        financials = fetch_finviz_financials(symbol)
    except FinvizError as exc:
        financials = {"summary": {}}
        notes.append(f"Finviz financials unavailable: {exc}")

    summary = financials.get("summary", {}) if isinstance(financials, dict) else {}
    valuation = {
        "pe": _metric(snapshot, "P/E") or summary.get("price_to_earnings"),
        "forward_pe": _metric(snapshot, "Forward P/E"),
        "ps": _metric(snapshot, "P/S") or summary.get("price_to_sales"),
        "pb": _metric(snapshot, "P/B"),
        "peg": _metric(snapshot, "PEG"),
    }
    profitability = {
        "profit_margin": _metric(snapshot, "Profit Margin"),
        "operating_margin": summary.get("operating_margin_pct"),
        "net_margin": summary.get("net_margin_pct"),
        "roe": _metric(snapshot, "ROE"),
        "roa": _metric(snapshot, "ROA"),
    }
    growth = {
        "eps_this_year": _metric(snapshot, "EPS this Y"),
        "eps_next_year": _metric(snapshot, "EPS next Y"),
        "sales_past_5y": _metric(snapshot, "Sales past 5Y"),
        "revenue_growth_pct": summary.get("revenue_growth_pct"),
    }
    ownership = {
        "institutional_ownership": _metric(snapshot, "Inst Own"),
        "insider_ownership": _metric(snapshot, "Insider Own"),
        "short_float": _metric(snapshot, "Short Float"),
    }
    if not notes:
        notes.append("Finviz public data parsed successfully.")
    return FundamentalSnapshot(
        ticker=symbol,
        source="finviz",
        valuation=valuation,
        profitability=profitability,
        growth=growth,
        ownership=ownership,
        notes=notes,
    )


def forward_returns_for_signals(rows: list[dict[str, Any]], *, periods: tuple[int, ...] = (5, 20, 60)) -> list[ForwardReturnResult]:
    results: list[ForwardReturnResult] = []
    for row in rows:
        ticker = str(row["ticker"]).upper()
        created_at = str(row["created_at"])
        try:
            history = fetch_history([ticker], period="2y")
            closes = close_prices(history, [ticker])
            close = closes[ticker].dropna()
            result = _forward_return_result(row, close, periods=periods)
        except Exception:
            result = ForwardReturnResult(
                signal_id=int(row["id"]),
                ticker=ticker,
                horizon=str(row["horizon"]),
                created_at=created_at,
                bias=str(row["bias"]),
                entry_price=None,
                returns={f"{period}d": None for period in periods},
                max_favorable_excursion_pct=None,
                max_adverse_excursion_pct=None,
                outcome="unavailable",
            )
        results.append(result)
    return results


def summarize_forward_returns(results: list[ForwardReturnResult]) -> dict[str, Any]:
    available = [result for result in results if result.entry_price is not None]
    if not available:
        return {"signals": len(results), "available": 0}
    win_count = sum(1 for result in available if result.outcome == "win")
    summary: dict[str, Any] = {
        "signals": len(results),
        "available": len(available),
        "win_rate": round(win_count / len(available), 4),
    }
    keys = sorted({key for result in available for key, value in result.returns.items() if value is not None})
    for key in keys:
        values = [float(result.returns[key]) for result in available if result.returns.get(key) is not None]
        if values:
            summary[f"avg_return_{key}"] = round(sum(values) / len(values), 4)
    return summary


def _screen_snapshot(snapshot: MarketSnapshot, recipe: str) -> ScreenResult:
    signal = score_snapshot(snapshot)
    score = signal.score
    reasons = list(signal.reasons[:3])
    if recipe == "momentum":
        score += snapshot.change_20d_pct / 10 + snapshot.change_60d_pct / 20
        if snapshot.rsi_14 > 75:
            score -= 1
            reasons.append("RSI is extended for a momentum entry.")
    elif recipe == "relative-strength":
        score += snapshot.change_60d_pct / 15
        reasons.append("Ranks by 60-day relative price strength.")
    elif recipe == "vcp":
        contraction_bonus = 2 if 40 <= snapshot.rsi_14 <= 70 and snapshot.volatility_20d < 40 else -1
        score += contraction_bonus + snapshot.change_60d_pct / 25
        reasons.append("Approximates VCP readiness with trend, moderate RSI, and contained volatility.")
    elif recipe == "earnings-gap":
        score += abs(snapshot.change_20d_pct) / 8
        reasons.append("Uses recent price displacement as a proxy pending explicit earnings-event data.")
    elif recipe == "quality-growth":
        score += 1 if snapshot.sma_200 is not None and snapshot.last_price > snapshot.sma_200 else 0
        reasons.append("Technical proxy until provider fundamentals are available.")
    elif recipe == "value-dividend":
        score -= max(0, snapshot.rsi_14 - 60) / 20
        score += 1 if snapshot.volatility_20d < 35 else 0
        reasons.append("Defensive proxy emphasizing lower volatility and non-extended entries.")
    return ScreenResult(
        ticker=snapshot.ticker,
        recipe=recipe,
        score=round(score, 2),
        signal=signal.label,
        confidence=signal.confidence,
        price=round(snapshot.last_price, 2),
        change_20d_pct=round(snapshot.change_20d_pct, 2),
        change_60d_pct=round(snapshot.change_60d_pct, 2),
        rsi_14=round(snapshot.rsi_14, 2),
        volatility_20d=round(snapshot.volatility_20d, 2),
        reasons=reasons,
    )


def _forward_return_result(row: dict[str, Any], close: pd.Series, *, periods: tuple[int, ...]) -> ForwardReturnResult:
    created_at = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    index = close.index
    position = 0
    for idx, value in enumerate(index):
        timestamp = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if timestamp >= created_at:
            position = idx
            break
    entry = float(close.iloc[position])
    bias = str(row["bias"])
    direction = -1 if "SHORT" in bias.upper() else 1
    returns: dict[str, float | None] = {}
    for period in periods:
        if position + period < len(close):
            raw = (float(close.iloc[position + period]) / entry - 1) * 100
            returns[f"{period}d"] = round(raw * direction, 2)
        else:
            returns[f"{period}d"] = None
    future = close.iloc[position : min(len(close), position + max(periods) + 1)]
    pct = ((future / entry - 1) * 100 * direction).tolist()
    mfe = max(pct) if pct else None
    mae = min(pct) if pct else None
    available_returns = [value for value in returns.values() if value is not None]
    outcome = "unavailable"
    if available_returns:
        outcome = "win" if available_returns[-1] > 0 else "loss" if available_returns[-1] < 0 else "flat"
    return ForwardReturnResult(
        signal_id=int(row["id"]),
        ticker=str(row["ticker"]),
        horizon=str(row["horizon"]),
        created_at=str(row["created_at"]),
        bias=bias,
        entry_price=round(entry, 2),
        returns=returns,
        max_favorable_excursion_pct=None if mfe is None else round(float(mfe), 2),
        max_adverse_excursion_pct=None if mae is None else round(float(mae), 2),
        outcome=outcome,
    )


def _pct_distance(value: float, reference: float) -> float:
    if reference == 0 or math.isnan(reference):
        return 0.0
    return (value / reference - 1) * 100


def _entry_zone(snapshot: MarketSnapshot, horizon: str) -> str:
    if horizon == "position":
        return f"Prefer pullbacks near the 50-day average around {snapshot.sma_50:.2f}, or a base breakout with fresh evidence."
    return f"Watch controlled pullbacks toward the 20-day average around {snapshot.sma_20:.2f}, or strength through recent highs."


def _invalidation(snapshot: MarketSnapshot, horizon: str) -> str:
    if horizon == "position" and snapshot.sma_200 is not None:
        return f"Reassess below the 200-day trend filter around {snapshot.sma_200:.2f} or if thesis evidence breaks."
    return f"Reassess on a decisive break below the 50-day average around {snapshot.sma_50:.2f}."


def _targets(snapshot: MarketSnapshot, horizon: str) -> list[str]:
    if horizon == "position":
        return ["Quarterly thesis review", f"Retest or exceed 52-week high near {snapshot.high_52w:.2f} if fundamentals confirm"]
    return [f"Retest recent 52-week high near {snapshot.high_52w:.2f}", "Trail risk if momentum fades"]


def _watch_items(snapshot: MarketSnapshot, horizon: str, signal: str) -> list[str]:
    items = [
        f"Signal label remains {signal}",
        f"RSI stays constructive without becoming exhausted: {snapshot.rsi_14:.1f}",
        f"20-day momentum: {snapshot.change_20d_pct:.1f}%",
    ]
    if horizon == "position":
        items.append("Next earnings, guidance, margin trend, valuation, and balance-sheet evidence.")
    else:
        items.append("Catalyst freshness, volume confirmation, and failed-breakout risk.")
    return items


def _metric(snapshot: dict[str, str], key: str) -> Optional[float | str]:
    value = snapshot.get(key)
    if value is None or value in {"-", ""}:
        return None
    text = value.replace("%", "").replace(",", "").strip()
    multiplier = 1.0
    if text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return round(float(text) * multiplier, 4)
    except ValueError:
        return value
