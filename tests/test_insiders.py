from types import SimpleNamespace

import pandas as pd
from typer.testing import CliRunner

from sadquant.cli import app
from sadquant.insiders import fetch_insider_activity
from sadquant.tools import default_registry


def test_fetch_insider_activity_summarizes_net_selling(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def get_insider_transactions(self):
            return pd.DataFrame(
                [
                    {
                        "Start Date": pd.Timestamp("2026-04-01"),
                        "Insider": "Jane CFO",
                        "Position": "Chief Financial Officer",
                        "Transaction": "Sale",
                        "Shares": 1000,
                        "Value": 250000,
                    }
                ]
            )

        def get_insider_purchases(self):
            return pd.DataFrame(
                [
                    {"Insider Purchases Last 6m": "Purchases", "Shares": 500, "Trans": 1},
                    {"Insider Purchases Last 6m": "Sales", "Shares": 2500, "Trans": 3},
                    {"Insider Purchases Last 6m": "Net Shares Purchased (Sold)", "Shares": -2000, "Trans": -2},
                ]
            )

        def get_insider_roster_holders(self):
            return pd.DataFrame(
                [
                    {
                        "Name": "Jane CFO",
                        "Position": "Chief Financial Officer",
                        "Latest Transaction Date": pd.Timestamp("2026-04-01"),
                    }
                ]
            )

    monkeypatch.setitem(__import__("sys").modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    activity = fetch_insider_activity("nvda")

    assert activity.ticker == "NVDA"
    assert activity.summary["bias"] == "net_selling"
    assert activity.summary["buy_shares"] == 500
    assert activity.summary["sell_shares"] == 2500
    assert activity.summary["net_shares"] == -2000
    assert activity.recent_transactions[0]["Start Date"] == "2026-04-01"


def test_default_registry_includes_insider_activity():
    assert "insider_activity" in default_registry().names()


def test_insiders_command_prints_summary(monkeypatch):
    monkeypatch.setattr(
        "sadquant.cli.fetch_insider_activity",
        lambda ticker, limit=12: SimpleNamespace(
            ticker=ticker.upper(),
            summary={
                "bias": "net_buying",
                "buy_shares": 1000.0,
                "sell_shares": 250.0,
                "net_shares": 750.0,
                "buy_transactions": 2.0,
                "sell_transactions": 1.0,
                "net_transactions": 1.0,
                "recent_transaction_count": 1,
            },
            recent_transactions=[
                {
                    "Start Date": "2026-04-01",
                    "Insider": "Jane CFO",
                    "Position": "CFO",
                    "Transaction": "Purchase",
                    "Text": "Buy",
                    "Shares": 1000,
                    "Value": 100000,
                    "Ownership": "D",
                }
            ],
            net_purchase_activity=[{"Period": "Purchases", "Shares": 1000, "Trans": 2}],
        ),
    )

    result = CliRunner().invoke(app, ["insiders", "NVDA"])

    assert result.exit_code == 0
    assert "Insider Activity Summary" in result.output
    assert "Net Buying" in result.output or "net_buying" in result.output
