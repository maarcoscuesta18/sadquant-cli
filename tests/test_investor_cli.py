import json

import pandas as pd
from typer.testing import CliRunner

from sadquant.cli import app
from sadquant.investor import forward_returns_for_signals, summarize_forward_returns
from sadquant.investor_state import InvestorState
from sadquant.models import MarketSnapshot, RiskSnapshot, SetupPlan, Signal
from sadquant.output import to_plain_data


def snapshot(ticker="TEST", **overrides):
    data = {
        "ticker": ticker,
        "last_price": 120.0,
        "change_20d_pct": 8.0,
        "change_60d_pct": 12.0,
        "rsi_14": 62.0,
        "sma_20": 115.0,
        "sma_50": 105.0,
        "sma_200": 90.0,
        "volatility_20d": 25.0,
        "high_52w": 125.0,
        "low_52w": 60.0,
        "observations": 252,
    }
    data.update(overrides)
    return MarketSnapshot(**data)


def test_investor_state_persists_watchlist_and_thesis(tmp_path):
    state = InvestorState(tmp_path / "investor.sqlite")

    watchlist = state.add_watchlist_tickers("Semis", ["nvda", "AMD", "NVDA"])
    thesis_id = state.add_thesis(ticker="NVDA", horizon="position", thesis="Durable AI demand")

    assert watchlist.name == "semis"
    assert watchlist.tickers == ["AMD", "NVDA"]
    assert state.get_watchlist("semis").tickers == ["AMD", "NVDA"]
    assert state.list_theses()[0].id == thesis_id


def test_watchlist_cli_json_output_uses_persistent_state(monkeypatch, tmp_path):
    state = InvestorState(tmp_path / "investor.sqlite")
    monkeypatch.setattr("sadquant.cli.InvestorState", lambda: state)

    result = CliRunner().invoke(app, ["watchlist", "add", "semis", "NVDA", "AMD", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "semis"
    assert payload["tickers"] == ["AMD", "NVDA"]


def test_setup_command_json_output(monkeypatch):
    plan = SetupPlan(
        ticker="NVDA",
        horizon="swing",
        signal=Signal(ticker="NVDA", label="LONG_BIAS", score=3.0, confidence=0.6, reasons=["trend"], risks=[]),
        snapshot=snapshot("NVDA"),
        risk=RiskSnapshot(
            ticker="NVDA",
            volatility_20d=25.0,
            distance_from_52w_high_pct=-4.0,
            distance_from_52w_low_pct=100.0,
            drawdown_from_high_pct=-4.0,
            risk_label="normal",
            notes=["ok"],
        ),
        bias="LONG_BIAS",
        entry_zone="near 20dma",
        invalidation="below 50dma",
        targets=["52w high"],
        watch_items=["volume"],
        data_gaps=[],
    )
    monkeypatch.setattr("sadquant.cli.build_setup_plan", lambda ticker, horizon="swing", period="1y": plan)

    result = CliRunner().invoke(app, ["setup", "NVDA", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ticker"] == "NVDA"
    assert payload["signal"]["label"] == "LONG_BIAS"
    assert payload["journal_signal_id"] is None


def test_screen_command_uses_named_recipe(monkeypatch):
    monkeypatch.setattr("sadquant.cli._resolve_investor_tickers", lambda universe, tickers=None: ["AAA", "BBB"])
    monkeypatch.setattr(
        "sadquant.cli.fetch_snapshots",
        lambda selected, period="1y": [
            snapshot("AAA", change_20d_pct=12.0, change_60d_pct=20.0),
            snapshot("BBB", change_20d_pct=-2.0, change_60d_pct=4.0),
        ],
    )

    result = CliRunner().invoke(app, ["screen", "--universe", "semis", "--recipe", "momentum", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["ticker"] == "AAA"
    assert payload[0]["recipe"] == "momentum"


def test_forward_returns_for_signals_uses_direction(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=80, freq="D")
    prices = pd.DataFrame({"Close": range(100, 180)}, index=dates)

    monkeypatch.setattr("sadquant.investor.fetch_history", lambda tickers, period="2y": prices)
    rows = [
        {
            "id": 1,
            "ticker": "AAA",
            "horizon": "swing",
            "created_at": "2026-01-01T00:00:00+00:00",
            "bias": "LONG_BIAS",
        }
    ]

    results = forward_returns_for_signals(rows)
    summary = summarize_forward_returns(results)

    assert results[0].returns["20d"] > 0
    assert results[0].outcome == "win"
    assert summary["available"] == 1
