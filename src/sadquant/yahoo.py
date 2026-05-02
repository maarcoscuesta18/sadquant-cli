from __future__ import annotations

import contextlib
import io
import logging
import warnings
from datetime import date, datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

from sadquant.market_data import MarketDataError


class YahooResearchError(MarketDataError):
    pass


TABLE_ROW_LIMIT = 12
HISTORY_ROW_LIMIT = 60
NEWS_LIMIT = 12
OPTION_EXPIRATION_LIMIT = 4
OPTION_ROW_LIMIT = 12
SHARES_ROW_LIMIT = 24


def fetch_yahoo_research(ticker: str) -> dict[str, Any]:
    """Fetch a broad public Yahoo Finance research packet for one ticker."""
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise YahooResearchError("Missing dependency `yfinance`. Install with `python -m pip install -e .` first.") from exc

    symbol = ticker.upper()
    try:
        yahoo_ticker = yf.Ticker(symbol)
    except Exception as exc:
        raise YahooResearchError(f"Could not initialize Yahoo Finance ticker for {symbol}: {exc}") from exc

    return {
        "ticker": symbol,
        "source": "yfinance",
        "limits": {
            "table_rows": TABLE_ROW_LIMIT,
            "history_rows": HISTORY_ROW_LIMIT,
            "news_items": NEWS_LIMIT,
            "option_expirations": OPTION_EXPIRATION_LIMIT,
            "option_rows_per_side": OPTION_ROW_LIMIT,
        },
        "price_history": {
            "history": _section(lambda: yahoo_ticker.history(period="1y", auto_adjust=False, actions=True), row_limit=HISTORY_ROW_LIMIT, tail=True),
            "history_metadata": _section(yahoo_ticker.get_history_metadata),
            "fast_info": _section(lambda: _mapping(yahoo_ticker.fast_info)),
            "info": _section(yahoo_ticker.get_info),
            "dividends": _section(yahoo_ticker.get_dividends, tail=True),
            "splits": _section(yahoo_ticker.get_splits, tail=True),
            "actions": _section(yahoo_ticker.get_actions, tail=True),
            "capital_gains": _section(yahoo_ticker.get_capital_gains, tail=True),
            "shares_full": _section(yahoo_ticker.get_shares_full, row_limit=SHARES_ROW_LIMIT, tail=True),
        },
        "financials": {
            "income_stmt": _section(yahoo_ticker.get_income_stmt),
            "quarterly_income_stmt": _section(lambda: yahoo_ticker.quarterly_income_stmt),
            "ttm_income_stmt": _section(lambda: yahoo_ticker.ttm_income_stmt),
            "balance_sheet": _section(yahoo_ticker.get_balance_sheet),
            "quarterly_balance_sheet": _section(lambda: yahoo_ticker.quarterly_balance_sheet),
            "cashflow": _section(yahoo_ticker.get_cashflow),
            "quarterly_cashflow": _section(lambda: yahoo_ticker.quarterly_cashflow),
            "ttm_cashflow": _section(lambda: yahoo_ticker.ttm_cashflow),
        },
        "earnings_events": {
            "earnings": _unavailable("Deprecated by yfinance; use financials.income_stmt Net Income instead."),
            "earnings_dates": _section(lambda: _call_with_optional_limit(yahoo_ticker.get_earnings_dates, NEWS_LIMIT)),
            "calendar": _section(lambda: yahoo_ticker.calendar),
            "sec_filings": _section(yahoo_ticker.get_sec_filings),
        },
        "analysis": {
            "analyst_price_targets": _section(yahoo_ticker.get_analyst_price_targets),
            "recommendations": _section(yahoo_ticker.get_recommendations),
            "recommendations_summary": _section(yahoo_ticker.get_recommendations_summary),
            "upgrades_downgrades": _section(yahoo_ticker.get_upgrades_downgrades),
            "earnings_estimate": _section(yahoo_ticker.get_earnings_estimate),
            "revenue_estimate": _section(yahoo_ticker.get_revenue_estimate),
            "earnings_history": _section(yahoo_ticker.get_earnings_history),
            "eps_trend": _section(yahoo_ticker.get_eps_trend),
            "eps_revisions": _section(yahoo_ticker.get_eps_revisions),
            "growth_estimates": _section(yahoo_ticker.get_growth_estimates),
        },
        "ownership": {
            "major_holders": _section(yahoo_ticker.get_major_holders),
            "institutional_holders": _section(yahoo_ticker.get_institutional_holders),
            "mutualfund_holders": _section(yahoo_ticker.get_mutualfund_holders),
            "insider_transactions": _section(yahoo_ticker.get_insider_transactions),
            "insider_purchases": _section(yahoo_ticker.get_insider_purchases),
            "insider_roster_holders": _section(yahoo_ticker.get_insider_roster_holders),
        },
        "public_context": {
            "isin": _section(yahoo_ticker.get_isin),
            "sustainability": _section(yahoo_ticker.get_sustainability),
            "funds_data": _section(lambda: _object_mapping(yahoo_ticker.get_funds_data())),
            "news": _section(yahoo_ticker.get_news, row_limit=NEWS_LIMIT),
        },
        "options": _options_section(yahoo_ticker),
    }


def _section(
    getter: Callable[[], Any],
    *,
    row_limit: int = TABLE_ROW_LIMIT,
    tail: bool = False,
) -> dict[str, Any]:
    try:
        value, messages = _quiet_yfinance_call(getter)
    except Exception as exc:
        return _unavailable(str(exc), type(exc).__name__)

    if _is_empty(value):
        return _unavailable("No data returned by Yahoo Finance.", messages=messages)

    payload = {"status": "available", "data": _serialize(value, row_limit=row_limit, tail=tail)}
    if messages:
        payload["messages"] = messages
    return payload


def _options_section(yahoo_ticker: Any) -> dict[str, Any]:
    try:
        expirations, messages = _quiet_yfinance_call(lambda: list(yahoo_ticker.options or []))
    except Exception as exc:
        return _unavailable(str(exc), type(exc).__name__)

    if not expirations:
        return _unavailable("No option expirations returned by Yahoo Finance.", messages=messages)

    included: list[dict[str, Any]] = []
    for expiration in expirations[:OPTION_EXPIRATION_LIMIT]:
        try:
            chain, chain_messages = _quiet_yfinance_call(lambda expiration=expiration: yahoo_ticker.option_chain(expiration))
            included.append(
                {
                    "expiration": expiration,
                    "calls": _serialize(chain.calls, row_limit=OPTION_ROW_LIMIT),
                    "puts": _serialize(chain.puts, row_limit=OPTION_ROW_LIMIT),
                    "messages": chain_messages,
                }
            )
        except Exception as exc:
            included.append(
                {
                    "expiration": expiration,
                    "status": "unavailable",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )

    return {
        "status": "available",
        "total_expirations": len(expirations),
        "included_expirations": len(included),
        "omitted_expirations": max(len(expirations) - len(included), 0),
        "messages": messages,
        "expirations": included,
    }


def _quiet_yfinance_call(getter: Callable[[], Any]) -> tuple[Any, list[str]]:
    stream = io.StringIO()
    logger = logging.getLogger("yfinance")
    previous_level = logger.level
    previous_disabled = logger.disabled
    logger.setLevel(logging.CRITICAL + 1)
    logger.disabled = True
    try:
        with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stderr(stream):
            warnings.simplefilter("ignore", DeprecationWarning)
            value = getter()
    finally:
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled

    messages = [str(warning.message) for warning in caught]
    stderr = stream.getvalue().strip()
    if stderr:
        messages.extend(line.strip() for line in stderr.splitlines() if line.strip())
    return value, messages


def _serialize(value: Any, *, row_limit: int = TABLE_ROW_LIMIT, tail: bool = False) -> Any:
    if isinstance(value, pd.DataFrame):
        return _serialize_frame(value, row_limit=row_limit, tail=tail)
    if isinstance(value, pd.Series):
        return _serialize_series(value, row_limit=row_limit, tail=tail)
    if isinstance(value, dict):
        return {str(_scalar(key)): _serialize(item, row_limit=row_limit, tail=tail) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        limited = list(value)[:row_limit]
        return {
            "items": [_serialize(item, row_limit=row_limit, tail=tail) for item in limited],
            "item_count": len(value),
            "omitted_items": max(len(value) - len(limited), 0),
        }
    return _scalar(value)


def _serialize_frame(frame: pd.DataFrame, *, row_limit: int, tail: bool) -> dict[str, Any]:
    limited = frame.tail(row_limit) if tail else frame.head(row_limit)
    records: list[dict[str, Any]] = []
    for index, row in limited.iterrows():
        record = {"index": _scalar(index)}
        for column, value in row.items():
            record[str(_scalar(column))] = _scalar(value)
        records.append(record)
    return {
        "columns": [str(_scalar(column)) for column in frame.columns],
        "index_name": None if frame.index.name is None else str(frame.index.name),
        "row_count": int(len(frame)),
        "returned_rows": len(records),
        "omitted_rows": max(len(frame) - len(records), 0),
        "truncated": len(records) < len(frame),
        "records": records,
    }


def _serialize_series(series: pd.Series, *, row_limit: int, tail: bool) -> dict[str, Any]:
    limited = series.tail(row_limit) if tail else series.head(row_limit)
    records = [{"index": _scalar(index), "value": _scalar(value)} for index, value in limited.items()]
    return {
        "name": None if series.name is None else str(series.name),
        "row_count": int(len(series)),
        "returned_rows": len(records),
        "omitted_rows": max(len(series) - len(records), 0),
        "truncated": len(records) < len(series),
        "records": records,
    }


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        return _object_mapping(value)


def _object_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    result: dict[str, Any] = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            item = getattr(value, name)
        except Exception:
            continue
        if callable(item):
            continue
        result[name] = item
        if len(result) >= 30:
            break
    return result


def _call_with_optional_limit(func: Callable[..., Any], limit: int) -> Any:
    try:
        return func(limit=limit)
    except TypeError:
        return func()


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return value.empty
    if isinstance(value, (dict, list, tuple, set, str)):
        return len(value) == 0
    return False


def _unavailable(reason: str, error_type: str | None = None, messages: list[str] | None = None) -> dict[str, Any]:
    payload = {"status": "unavailable", "reason": reason}
    if error_type is not None:
        payload["error_type"] = error_type
    if messages:
        payload["messages"] = messages
    return payload
