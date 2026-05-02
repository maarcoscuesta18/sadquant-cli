import json
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

from sadquant.tools import default_registry
from sadquant.yahoo import OPTION_EXPIRATION_LIMIT, OPTION_ROW_LIMIT, fetch_yahoo_research


class FakeFundsData:
    def __init__(self):
        self.asset_classes = pd.DataFrame([{"category": "equity", "weight": np.float64(0.9)}])
        self.description = "fund data"


class FakeTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.options = ["2026-05-15", "2026-06-19", "2026-07-17", "2026-08-21", "2026-09-18"]
        self.quarterly_income_stmt = pd.DataFrame(
            {pd.Timestamp("2026-03-31"): [np.int64(10), pd.NA]},
            index=["Total Revenue", "Net Income"],
        )
        self.ttm_income_stmt = pd.DataFrame({"ttm": [40]}, index=["Total Revenue"])
        self.quarterly_balance_sheet = pd.DataFrame({"2026-03-31": [5]}, index=["Cash And Cash Equivalents"])
        self.quarterly_cashflow = pd.DataFrame({"2026-03-31": [3]}, index=["Free Cash Flow"])
        self.ttm_cashflow = pd.DataFrame({"ttm": [12]}, index=["Free Cash Flow"])
        self.calendar = {"Earnings Date": [pd.Timestamp("2026-05-01")]}

    def history(self, period, auto_adjust, actions):
        return pd.DataFrame(
            {
                "Open": np.arange(20, dtype=np.int64),
                "Close": np.arange(20, dtype=np.float64),
                "Volume": np.arange(20, dtype=np.int64),
            },
            index=pd.date_range("2026-01-01", periods=20, tz="America/New_York"),
        )

    def get_history_metadata(self):
        return {"exchangeTimezoneName": "America/New_York", "regularMarketTime": pd.Timestamp("2026-04-24")}

    @property
    def fast_info(self):
        return {"lastPrice": np.float64(101.25), "marketCap": np.int64(1_000_000)}

    def get_info(self):
        print("HTTP Error 404: fake fundamentals gap", file=sys.stderr)
        return {"shortName": "Fake Inc.", "sector": "Technology", "currentPrice": np.float64(101.25)}

    def get_dividends(self):
        return pd.Series([0.1, 0.2], index=pd.date_range("2025-01-01", periods=2), name="Dividends")

    def get_splits(self):
        return pd.Series([2], index=[pd.Timestamp("2025-06-01")], name="Stock Splits")

    def get_actions(self):
        return pd.DataFrame({"Dividends": [0.2], "Stock Splits": [0]}, index=[pd.Timestamp("2025-01-01")])

    def get_capital_gains(self):
        return pd.Series(dtype=float)

    def get_shares_full(self):
        return pd.Series([np.int64(100), np.int64(110)], index=pd.date_range("2025-01-01", periods=2), name="Shares")

    def get_income_stmt(self):
        return pd.DataFrame({"2025": [100, 20]}, index=["Total Revenue", "Net Income"])

    def get_balance_sheet(self):
        return pd.DataFrame({"2025": [50, 10]}, index=["Total Assets", "Total Debt"])

    def get_cashflow(self):
        return pd.DataFrame({"2025": [30, -5]}, index=["Operating Cash Flow", "Capital Expenditure"])

    def get_earnings(self):
        return pd.DataFrame({"Revenue": [100], "Earnings": [20]}, index=[2025])

    def get_earnings_dates(self, limit=12):
        return pd.DataFrame({"EPS Estimate": [1.2], "Reported EPS": [1.3]}, index=[pd.Timestamp("2026-04-01")])

    def get_sec_filings(self):
        return [{"date": pd.Timestamp("2026-02-01"), "type": "10-K"}]

    def get_analyst_price_targets(self):
        return {"current": 101.25, "mean": 120.0}

    def get_recommendations(self):
        return pd.DataFrame({"strongBuy": [4], "buy": [10]}, index=["0m"])

    def get_recommendations_summary(self):
        return pd.DataFrame({"strongBuy": [4], "buy": [10]}, index=["0m"])

    def get_upgrades_downgrades(self):
        return pd.DataFrame({"Firm": ["Desk"], "ToGrade": ["Buy"]}, index=[pd.Timestamp("2026-01-15")])

    def get_earnings_estimate(self):
        return pd.DataFrame({"avg": [1.2], "growth": [0.1]}, index=["0q"])

    def get_revenue_estimate(self):
        return pd.DataFrame({"avg": [100]}, index=["0q"])

    def get_earnings_history(self):
        return pd.DataFrame({"epsEstimate": [1.0], "epsActual": [1.1]}, index=[pd.Timestamp("2026-01-01")])

    def get_eps_trend(self):
        return pd.DataFrame({"current": [1.2]}, index=["0q"])

    def get_eps_revisions(self):
        return pd.DataFrame({"upLast7days": [1]}, index=["0q"])

    def get_growth_estimates(self):
        return pd.DataFrame({"stockTrend": [0.2]}, index=["0q"])

    def get_major_holders(self):
        return pd.DataFrame({"Breakdown": ["insidersPercentHeld"], "Value": [0.02]})

    def get_institutional_holders(self):
        return pd.DataFrame({"Holder": ["Fund"], "Shares": [np.int64(1000)]})

    def get_mutualfund_holders(self):
        return pd.DataFrame({"Holder": ["Mutual"], "Shares": [np.int64(500)]})

    def get_insider_transactions(self):
        return pd.DataFrame({"Insider": ["CFO"], "Shares": [100]})

    def get_insider_purchases(self):
        return pd.DataFrame({"Label": ["Purchases"], "Shares": [100]})

    def get_insider_roster_holders(self):
        return pd.DataFrame({"Name": ["CFO"], "Position": ["Chief Financial Officer"]})

    def get_isin(self):
        return "US0000000000"

    def get_sustainability(self):
        raise RuntimeError("ESG unavailable")

    def get_funds_data(self):
        return FakeFundsData()

    def get_news(self):
        return [{"title": "Headline", "providerPublishTime": pd.Timestamp("2026-04-01")}]

    def option_chain(self, expiration):
        rows = OPTION_ROW_LIMIT + 3
        calls = pd.DataFrame({"strike": np.arange(rows), "lastPrice": np.arange(rows, dtype=float)})
        puts = pd.DataFrame({"strike": np.arange(rows), "lastPrice": np.arange(rows, dtype=float)})
        return SimpleNamespace(calls=calls, puts=puts)


def test_fetch_yahoo_research_collects_sections_and_serializes_json(monkeypatch, capsys):
    monkeypatch.setitem(__import__("sys").modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    payload = fetch_yahoo_research("nvda")

    assert payload["ticker"] == "NVDA"
    assert payload["price_history"]["history"]["status"] == "available"
    assert payload["price_history"]["history"]["data"]["row_count"] == 20
    assert payload["price_history"]["info"]["messages"] == ["HTTP Error 404: fake fundamentals gap"]
    assert payload["price_history"]["capital_gains"]["status"] == "unavailable"
    assert payload["financials"]["quarterly_income_stmt"]["data"]["records"][1]["2026-03-31T00:00:00"] is None
    assert payload["earnings_events"]["earnings"]["status"] == "unavailable"
    assert "Deprecated by yfinance" in payload["earnings_events"]["earnings"]["reason"]
    assert payload["public_context"]["sustainability"]["status"] == "unavailable"
    assert payload["options"]["total_expirations"] == 5
    assert payload["options"]["included_expirations"] == OPTION_EXPIRATION_LIMIT
    assert payload["options"]["expirations"][0]["calls"]["returned_rows"] == OPTION_ROW_LIMIT

    json.dumps(payload, allow_nan=False)
    captured = capsys.readouterr()
    assert "HTTP Error 404" not in captured.err


def test_default_registry_includes_yahoo_research():
    assert "yahoo_research" in default_registry().names()
