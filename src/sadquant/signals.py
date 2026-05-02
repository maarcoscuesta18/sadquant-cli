from __future__ import annotations

from sadquant.models import MarketSnapshot, Signal


def score_components(snapshot: MarketSnapshot, context_hits: int = 0) -> dict[str, float]:
    trend = 0.0
    momentum = 0.0
    risk = 0.0
    context = 0.25 if context_hits else 0.0

    if snapshot.last_price > snapshot.sma_20 > snapshot.sma_50:
        trend += 2.0
    elif snapshot.last_price < snapshot.sma_20 < snapshot.sma_50:
        trend -= 2.0
    if snapshot.sma_200 is not None:
        trend += 1.0 if snapshot.last_price > snapshot.sma_200 else -1.0
    if snapshot.change_20d_pct > 5:
        momentum += 1.0
    elif snapshot.change_20d_pct < -5:
        momentum -= 1.0
    if snapshot.rsi_14 >= 75:
        risk -= 0.75
    elif snapshot.rsi_14 <= 25:
        risk += 0.75
    return {
        "trend": trend,
        "momentum": momentum,
        "risk": risk,
        "valuation_quality": 0.0,
        "earnings_revisions": 0.0,
        "liquidity": 0.0,
        "catalyst_freshness": 0.0,
        "data_completeness": context,
    }


def score_snapshot(snapshot: MarketSnapshot, context_hits: int = 0) -> Signal:
    score = 0.0
    reasons: list[str] = []
    risks: list[str] = []

    if snapshot.last_price > snapshot.sma_20 > snapshot.sma_50:
        score += 2.0
        reasons.append("Price is above rising short/intermediate moving averages.")
    elif snapshot.last_price < snapshot.sma_20 < snapshot.sma_50:
        score -= 2.0
        reasons.append("Price is below falling short/intermediate moving averages.")

    if snapshot.sma_200 is not None:
        if snapshot.last_price > snapshot.sma_200:
            score += 1.0
            reasons.append("Price is above the 200-day trend filter.")
        else:
            score -= 1.0
            reasons.append("Price is below the 200-day trend filter.")

    if snapshot.change_20d_pct > 5:
        score += 1.0
        reasons.append(f"20-day momentum is positive at {snapshot.change_20d_pct:.1f}%.")
    elif snapshot.change_20d_pct < -5:
        score -= 1.0
        reasons.append(f"20-day momentum is negative at {snapshot.change_20d_pct:.1f}%.")

    if snapshot.rsi_14 >= 75:
        score -= 0.75
        risks.append(f"RSI is extended at {snapshot.rsi_14:.1f}; pullback risk is elevated.")
    elif snapshot.rsi_14 <= 25:
        score += 0.75
        risks.append(f"RSI is washed out at {snapshot.rsi_14:.1f}; short-covering risk is elevated.")

    if snapshot.volatility_20d > 55:
        score *= 0.8
        risks.append(f"20-day annualized volatility is high at {snapshot.volatility_20d:.1f}%.")

    if context_hits:
        reasons.append(f"{context_hits} local RAG context item(s) were retrieved for this ticker.")

    if score >= 2.0:
        label = "LONG_BIAS"
    elif score <= -2.0:
        label = "SHORT_BIAS"
    else:
        label = "NEUTRAL"

    confidence = min(0.95, max(0.15, abs(score) / 5))
    if not reasons:
        reasons.append("No strong trend or momentum edge detected.")

    return Signal(
        ticker=snapshot.ticker,
        label=label,
        score=round(score, 2),
        confidence=round(confidence, 2),
        reasons=reasons,
        risks=risks,
    )
