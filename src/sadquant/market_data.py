from __future__ import annotations

import math

import pandas as pd
import numpy as np

from sadquant.models import MarketSnapshot


class MarketDataError(RuntimeError):
    pass


def _rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    value = 100 - (100 / (1 + rs.iloc[-1]))
    if pd.isna(value):
        return 50.0
    return float(value)


def _pct_change(close: pd.Series, periods: int) -> float:
    if len(close) <= periods:
        return 0.0
    return float((close.iloc[-1] / close.iloc[-periods] - 1) * 100)


def fetch_history(tickers: list[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    if not tickers:
        raise MarketDataError("No tickers provided.")

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise MarketDataError("Missing dependency `yfinance`. Install with `python -m pip install -e .` first.") from exc

    data = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if data.empty:
        raise MarketDataError("No market data returned. Check tickers, period, or network access.")
    return data


def close_prices(data: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if isinstance(data.columns, pd.MultiIndex):
        closes = data["Close"]
    else:
        closes = data[["Close"]].rename(columns={"Close": tickers[0]})
    return closes.dropna(axis=1, how="all")


def build_snapshot(ticker: str, close: pd.Series) -> MarketSnapshot:
    clean = close.dropna()
    if len(clean) < 60:
        raise MarketDataError(f"{ticker} has insufficient data: {len(clean)} observations.")

    returns = np.log(clean / clean.shift(1)).dropna()
    sma_20 = float(clean.rolling(20).mean().iloc[-1])
    sma_50 = float(clean.rolling(50).mean().iloc[-1])
    sma_200_value = clean.rolling(200).mean().iloc[-1] if len(clean) >= 200 else math.nan

    return MarketSnapshot(
        ticker=ticker,
        last_price=float(clean.iloc[-1]),
        change_20d_pct=_pct_change(clean, 20),
        change_60d_pct=_pct_change(clean, 60),
        rsi_14=_rsi(clean),
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=None if pd.isna(sma_200_value) else float(sma_200_value),
        volatility_20d=float(returns.tail(20).std() * np.sqrt(252) * 100),
        high_52w=float(clean.tail(252).max()),
        low_52w=float(clean.tail(252).min()),
        observations=len(clean),
    )


def fetch_snapshots(tickers: list[str], period: str = "1y") -> list[MarketSnapshot]:
    data = fetch_history(tickers, period=period)
    closes = close_prices(data, tickers)
    snapshots: list[MarketSnapshot] = []
    for ticker in tickers:
        if ticker in closes:
            try:
                snapshots.append(build_snapshot(ticker, closes[ticker]))
            except MarketDataError:
                continue
    return snapshots


def correlation(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    data = fetch_history(tickers, period=period)
    closes = close_prices(data, tickers).dropna(axis=1, thresh=60)
    returns = np.log(closes / closes.shift(1)).dropna()
    if returns.empty:
        raise MarketDataError("Not enough overlapping observations for correlation.")
    return returns.corr()
