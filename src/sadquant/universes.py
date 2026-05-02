from __future__ import annotations

from typing import Optional

UNIVERSES: dict[str, list[str]] = {
    "etf": ["SPY", "QQQ", "IWM", "DIA", "VTI", "TLT", "HYG", "LQD", "ARKK", "XLF", "XLK", "XLE"],
    "gold": ["GLD", "IAU", "GDX", "GDXJ", "NEM", "AEM", "GOLD", "GC=F", "SI=F"],
    "semis": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MU", "INTC", "QCOM", "SMH", "SOXX"],
    "indexes": ["SPY", "QQQ", "IWM", "DIA", "^GSPC", "^IXIC", "^RUT", "^VIX", "TLT", "DXY"],
}

UNIVERSES["all"] = sorted({ticker for tickers in UNIVERSES.values() for ticker in tickers})


def resolve_universe(name: str, extra_tickers: Optional[list[str]] = None) -> list[str]:
    normalized = name.lower().strip()
    if normalized not in UNIVERSES:
        valid = ", ".join(sorted(UNIVERSES))
        raise ValueError(f"Unknown universe '{name}'. Valid universes: {valid}")

    tickers = list(UNIVERSES[normalized])
    if extra_tickers:
        tickers.extend(t.upper().strip() for t in extra_tickers if t.strip())
    return sorted(dict.fromkeys(tickers))
