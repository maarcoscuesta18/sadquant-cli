from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from sadquant.market_data import MarketDataError


OHLC_COLUMNS = ["Open", "High", "Low", "Close"]
OPTIONAL_COLUMNS = ["Volume"]


@dataclass(frozen=True)
class ChartGlyphs:
    up_body: str
    down_body: str
    wick: str
    flat_body: str
    volume_bars: str


UNICODE_GLYPHS = ChartGlyphs(
    up_body="█",
    down_body="█",
    wick="│",
    flat_body="─",
    volume_bars="▁▂▃▄▅▆▇█",
)

ASCII_GLYPHS = ChartGlyphs(
    up_body="#",
    down_body="#",
    wick="|",
    flat_body="-",
    volume_bars=" .:-=+*#",
)


def normalize_ohlcv(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Return a single-ticker OHLCV frame from yfinance output."""
    if data.empty:
        raise MarketDataError("No market data returned. Check ticker, period, or network access.")

    symbol = ticker.upper()
    normalized: dict[str, pd.Series] = {}
    for column in [*OHLC_COLUMNS, *OPTIONAL_COLUMNS]:
        series = _select_column(data, column, symbol)
        if series is not None:
            normalized[column] = pd.to_numeric(series, errors="coerce")

    missing = [column for column in OHLC_COLUMNS if column not in normalized]
    if missing:
        raise MarketDataError(f"Missing OHLC columns for {symbol}: {', '.join(missing)}.")
    if "Volume" not in normalized:
        normalized["Volume"] = pd.Series(0.0, index=data.index)

    frame = pd.DataFrame(normalized, index=data.index)
    frame = frame.dropna(subset=OHLC_COLUMNS)
    if frame.empty:
        raise MarketDataError(f"No usable OHLC rows returned for {symbol}.")
    return frame[[*OHLC_COLUMNS, "Volume"]]


def downsample_ohlcv(frame: pd.DataFrame, max_points: int) -> pd.DataFrame:
    """Compress OHLCV rows while preserving candle semantics."""
    if max_points < 1:
        raise ValueError("max_points must be at least 1.")
    if len(frame) <= max_points:
        return frame.copy()

    rows = []
    index = []
    for bucket in np.array_split(np.arange(len(frame)), max_points):
        chunk = frame.iloc[bucket]
        rows.append(
            {
                "Open": float(chunk["Open"].iloc[0]),
                "High": float(chunk["High"].max()),
                "Low": float(chunk["Low"].min()),
                "Close": float(chunk["Close"].iloc[-1]),
                "Volume": float(chunk["Volume"].sum()),
            }
        )
        index.append(chunk.index[-1])
    return pd.DataFrame(rows, index=index)


def render_candlestick_chart(
    ticker: str,
    data: pd.DataFrame,
    *,
    period: str,
    interval: str,
    height: int = 18,
    width: int = 80,
    include_volume: bool = True,
    plain: bool = False,
) -> str:
    if height < 6:
        raise ValueError("Chart height must be at least 6.")

    glyphs = _resolve_glyphs()

    label_width = 10
    chart_width = width - label_width - 1
    if chart_width < 12:
        raise ValueError("Terminal is too narrow for a chart. Use a wider terminal or pass a larger --width.")

    candles = downsample_ohlcv(data, chart_width)
    if candles.empty:
        raise MarketDataError(f"No usable OHLC rows returned for {ticker.upper()}.")

    low = float(candles["Low"].min())
    high = float(candles["High"].max())
    if high == low:
        padding = max(abs(high) * 0.01, 1.0)
        low -= padding
        high += padding

    grid = [[" " for _ in range(len(candles))] for _ in range(height)]
    colors = [["" for _ in range(len(candles))] for _ in range(height)]

    for x, row in enumerate(candles.itertuples(index=False)):
        open_price = float(row.Open)
        high_price = float(row.High)
        low_price = float(row.Low)
        close_price = float(row.Close)
        high_row = _price_to_row(high_price, low, high, height)
        low_row = _price_to_row(low_price, low, high, height)
        open_row = _price_to_row(open_price, low, high, height)
        close_row = _price_to_row(close_price, low, high, height)
        color = "green" if close_price >= open_price else "red"

        for y in range(high_row, low_row + 1):
            grid[y][x] = glyphs.wick
            colors[y][x] = color

        if close_price == open_price:
            grid[open_row][x] = glyphs.flat_body
            colors[open_row][x] = color
            continue

        for y in range(min(open_row, close_row), max(open_row, close_row) + 1):
            grid[y][x] = glyphs.up_body if close_price > open_price else glyphs.down_body
            colors[y][x] = color

    first_close = float(candles["Close"].iloc[0])
    last_close = float(candles["Close"].iloc[-1])
    change = 0.0 if first_close == 0 else ((last_close / first_close) - 1) * 100
    header = (
        f"{ticker.upper()} {period} {interval} | {len(candles)} candles | "
        f"Last {last_close:,.2f} | Change {change:+.2f}%"
    )

    lines = [header]
    for y, cells in enumerate(grid):
        price = high - ((high - low) * y / (height - 1))
        row = "".join(_style_cell(cell, colors[y][x], plain) for x, cell in enumerate(cells))
        lines.append(f"{price:>{label_width},.2f} {row}")

    lines.append(f"{'':>{label_width}} {_date_axis(candles.index, len(candles))}")

    if include_volume:
        lines.append(f"{'Volume':>{label_width}} {_volume_axis(candles['Volume'], plain, glyphs)}")

    return "\n".join(lines)


def _select_column(data: pd.DataFrame, column: str, ticker: str) -> Optional[pd.Series]:
    if not isinstance(data.columns, pd.MultiIndex):
        if column in data.columns:
            return data[column]
        return None

    if column in data.columns.get_level_values(0):
        selected = data[column]
        if isinstance(selected, pd.Series):
            return selected
        if ticker in selected.columns:
            return selected[ticker]
        if len(selected.columns) == 1:
            return selected.iloc[:, 0]

    if column in data.columns.get_level_values(-1):
        selected_columns = [item for item in data.columns if item[-1] == column]
        if not selected_columns:
            return None
        for item in selected_columns:
            if ticker in item:
                return data[item]
        if len(selected_columns) == 1:
            return data[selected_columns[0]]

    return None


def _price_to_row(price: float, low: float, high: float, height: int) -> int:
    ratio = (high - price) / (high - low)
    return int(max(0, min(height - 1, round(ratio * (height - 1)))))


def _style_cell(cell: str, color: str, plain: bool) -> str:
    if plain or cell == " " or not color:
        return cell
    return f"[{color}]{cell}[/{color}]"


def _date_axis(index: pd.Index, width: int) -> str:
    if width <= 0:
        return ""
    labels = [
        (0, _format_date(index[0])),
        (width // 2, _format_date(index[len(index) // 2])),
        (width - 1, _format_date(index[-1])),
    ]
    chars = [" " for _ in range(width)]
    occupied_until = -1
    for position, label in labels:
        start = max(0, min(width - len(label), position - len(label) // 2))
        if start <= occupied_until:
            continue
        for offset, char in enumerate(label[: max(width - start, 0)]):
            chars[start + offset] = char
        occupied_until = start + len(label) - 1
    return "".join(chars).rstrip()


def _format_date(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.hour or timestamp.minute:
        return timestamp.strftime("%m-%d %H:%M")
    return timestamp.strftime("%Y-%m-%d")


def _volume_axis(volume: pd.Series, plain: bool, glyphs: ChartGlyphs) -> str:
    max_volume = float(volume.max())
    if max_volume <= 0:
        bars = " " * len(volume)
    else:
        bars = "".join(
            glyphs.volume_bars[min(len(glyphs.volume_bars) - 1, int((float(value) / max_volume) * (len(glyphs.volume_bars) - 1)))]
            for value in volume
        )
    if plain:
        return bars
    return f"[cyan]{bars}[/cyan]"


def _resolve_glyphs() -> ChartGlyphs:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "│█▁".encode(encoding)
    except UnicodeEncodeError:
        return ASCII_GLYPHS
    return UNICODE_GLYPHS
