import pandas as pd
from typer.testing import CliRunner

from sadquant.charts import downsample_ohlcv, normalize_ohlcv, render_candlestick_chart
from sadquant.cli import app
from sadquant.market_data import MarketDataError


class FakeStatus:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, *args, **kwargs):
        pass


def ohlcv_frame(rows=8):
    index = pd.date_range("2026-01-01", periods=rows)
    return pd.DataFrame(
        {
            "Open": [100 + value for value in range(rows)],
            "High": [103 + value for value in range(rows)],
            "Low": [99 + value for value in range(rows)],
            "Close": [102 + value for value in range(rows)],
            "Volume": [1_000 * (value + 1) for value in range(rows)],
        },
        index=index,
    )


def test_normalize_ohlcv_accepts_single_index_yfinance_frame():
    normalized = normalize_ohlcv(ohlcv_frame(), "nvda")

    assert list(normalized.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert normalized["Close"].iloc[-1] == 109


def test_normalize_ohlcv_accepts_multi_index_yfinance_frame():
    base = ohlcv_frame()
    data = pd.concat({"Open": base[["Open"]], "High": base[["High"]], "Low": base[["Low"]], "Close": base[["Close"]], "Volume": base[["Volume"]]}, axis=1)
    data.columns = pd.MultiIndex.from_tuples([(field, "NVDA") for field in ["Open", "High", "Low", "Close", "Volume"]])

    normalized = normalize_ohlcv(data, "NVDA")

    assert list(normalized.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert normalized["Open"].iloc[0] == 100
    assert normalized["Volume"].iloc[-1] == 8_000


def test_downsample_ohlcv_preserves_candle_semantics():
    sampled = downsample_ohlcv(ohlcv_frame(6), 3)

    assert len(sampled) == 3
    assert sampled["Open"].iloc[0] == 100
    assert sampled["High"].iloc[0] == 104
    assert sampled["Low"].iloc[0] == 99
    assert sampled["Close"].iloc[0] == 103
    assert sampled["Volume"].iloc[0] == 3_000


def test_render_candlestick_chart_outputs_plain_glyphs():
    output = render_candlestick_chart("TEST", ohlcv_frame(), period="1mo", interval="1d", height=6, width=36, plain=True)

    assert "TEST 1mo 1d" in output
    assert "█" in output
    assert "│" in output
    assert "Volume" in output
    assert "[green]" not in output


def test_chart_command_prints_candlestick_chart(monkeypatch):
    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.fetch_history", lambda tickers, period, interval: ohlcv_frame())

    result = CliRunner().invoke(app, ["chart", "NVDA", "--period", "1mo", "--interval", "1d", "--height", "6", "--width", "40", "--plain"])

    assert result.exit_code == 0
    assert "NVDA 1mo 1d" in result.output
    assert "█" in result.output
    assert "Volume" in result.output


def test_chart_command_can_hide_volume(monkeypatch):
    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.fetch_history", lambda tickers, period, interval: ohlcv_frame())

    result = CliRunner().invoke(app, ["chart", "NVDA", "--height", "6", "--width", "40", "--plain", "--no-volume"])

    assert result.exit_code == 0
    assert "Volume" not in result.output


def test_chart_command_reports_empty_data(monkeypatch):
    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.fetch_history", lambda tickers, period, interval: pd.DataFrame())

    result = CliRunner().invoke(app, ["chart", "NVDA", "--height", "6", "--width", "40", "--plain"])

    assert result.exit_code == 1
    assert isinstance(result.exception, MarketDataError)
