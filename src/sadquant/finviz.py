from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any, Dict, Optional

import httpx


class FinvizError(RuntimeError):
    pass


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


def fetch_finviz_snapshot(ticker: str) -> Dict[str, str]:
    """Fetch the Finviz quote snapshot table for a ticker.

    Finviz does not publish an official free API. This is a small read-only
    parser for the public quote page, so callers get an explicit error if the
    page structure changes instead of fabricated metrics.
    """
    metrics = _parse_snapshot_cells(_fetch_quote_page(ticker))
    if not metrics:
        raise FinvizError(f"Could not parse Finviz snapshot for {ticker.upper()}.")
    return metrics


def fetch_finviz_financials(ticker: str) -> Dict[str, Any]:
    """Fetch Finviz statement rows visible on the quote page.

    The public page exposes a compact statement table like the one shown in the
    UI: period columns, revenue, margins, EPS, EBITDA, and valuation ratios.
    """
    financials = _parse_financial_statement(_fetch_quote_page(ticker, quote_type="ea"))
    if not financials["rows"]:
        raise FinvizError(f"Could not parse Finviz financial statement for {ticker.upper()}.")
    return {"ticker": ticker.upper(), **financials}


def _fetch_quote_page(ticker: str, quote_type: Optional[str] = None) -> str:
    quote_type_param = f"&ty={quote_type}" if quote_type else ""
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}{quote_type_param}&p=d"
    with httpx.Client(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _parse_snapshot_cells(html: str) -> Dict[str, str]:
    parser = _SnapshotTableParser()
    parser.feed(html)
    cells = parser.cells
    if not cells:
        return {}

    metrics: Dict[str, str] = {}
    for index in range(0, len(cells) - 1, 2):
        key = cells[index].strip()
        value = cells[index + 1].strip()
        if key:
            metrics[key] = value
    return metrics


def _parse_financial_statement(html: str) -> Dict[str, Any]:
    parser = _AllTablesParser()
    parser.feed(html)
    statement_rows = _find_statement_rows(parser.tables)
    if not statement_rows:
        return _parse_financial_analysis_data(html)

    period_row = statement_rows[0]
    periods = [cell for cell in period_row[1:] if _is_period_label(cell)]
    if not periods:
        return {"periods": [], "rows": {}, "summary": {"bias": "unavailable"}}

    rows: dict[str, dict[str, str]] = {}
    for row in statement_rows[1:]:
        if len(row) < 2:
            continue
        label = row[0]
        values = _align_values_to_periods(row[1:], periods)
        if label and any(value != "-" for value in values):
            rows[label] = dict(zip(periods, values))

    return {
        "periods": periods,
        "rows": rows,
        "summary": _summarize_financial_rows(periods, rows),
    }


def _parse_financial_analysis_data(html: str) -> Dict[str, Any]:
    """Parse the current Finviz earnings/financial-analysis JSON payload.

    Finviz no longer emits the detailed statement rows in the static quote HTML
    for some tickers. The earnings tab still includes chart data for annual and
    quarterly EPS, sales, and shares in an application/json script tag.
    """
    payload = _extract_json_script(html, "fa-init-data-0")
    if not isinstance(payload, dict):
        return {"periods": [], "rows": {}, "summary": {"bias": "unavailable"}}

    annual_rows = _rows_from_fa_series(payload.get("annual", {}).get("values", []), annual=True)
    annual_periods = _order_annual_periods(_periods_from_rows(annual_rows))
    if not annual_rows or not annual_periods:
        return {"periods": [], "rows": {}, "summary": {"bias": "unavailable"}}

    quarterly_rows = _rows_from_fa_series(payload.get("quarterly", {}).get("values", []), annual=False)
    quarterly_periods = list(reversed(_periods_from_rows(quarterly_rows)))

    return {
        "periods": annual_periods,
        "rows": annual_rows,
        "quarterly_periods": quarterly_periods,
        "quarterly_rows": quarterly_rows,
        "summary": _summarize_financial_rows(annual_periods, annual_rows),
    }


def _extract_json_script(html: str, script_id: str) -> Any:
    parser = _JsonScriptParser(script_id)
    parser.feed(html)
    if not parser.data:
        return None
    try:
        return json.loads(parser.data)
    except json.JSONDecodeError:
        return None


_FA_SERIES_LABELS = {
    0: "EPS (Diluted)",
    1: "Total Revenue",
    2: "Shares Outstanding",
}


def _rows_from_fa_series(series_groups: Any, annual: bool) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not isinstance(series_groups, list):
        return rows

    for index, label in _FA_SERIES_LABELS.items():
        if index >= len(series_groups) or not isinstance(series_groups[index], list):
            continue
        row: dict[str, str] = {}
        for item in series_groups[index]:
            if not isinstance(item, dict) or "name" not in item or "value" not in item:
                continue
            period = _normalize_fa_period(str(item["name"]), annual=annual)
            row[period] = _format_fa_value(item["value"])
        if row:
            rows[label] = row
    return rows


def _normalize_fa_period(value: str, annual: bool) -> str:
    if annual and re.fullmatch(r"\d{4}", value):
        return f"FY {value}"
    return value


def _format_fa_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        text = f"{value:,.4f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text
    return str(value)


def _periods_from_rows(rows: dict[str, dict[str, str]]) -> list[str]:
    periods: list[str] = []
    for row in rows.values():
        for period in row:
            if period not in periods:
                periods.append(period)
    return periods


def _order_annual_periods(periods: list[str]) -> list[str]:
    ordered: list[str] = []
    if "TTM" in periods:
        ordered.append("TTM")

    fiscal_years = sorted(
        (period for period in periods if re.fullmatch(r"FY \d{4}", period)),
        key=lambda period: int(period.split()[1]),
        reverse=True,
    )
    ordered.extend(fiscal_years)
    ordered.extend(period for period in periods if period not in ordered)
    return ordered


def _find_statement_rows(tables: list[list[list[str]]]) -> list[list[str]]:
    for table in tables:
        if not table:
            continue
        first_row = table[0]
        labels = {row[0].lower() for row in table if row}
        if first_row and first_row[0].lower() == "period" and "total revenue" in labels:
            return table
    return []


def _is_period_label(value: str) -> bool:
    return value == "TTM" or value.startswith("FY ") or bool(re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value))


def _align_values_to_periods(values: list[str], periods: list[str]) -> list[str]:
    cleaned = [value for value in values if value and value != ""]
    if len(cleaned) > len(periods):
        cleaned = cleaned[-len(periods) :]
    return (["-"] * (len(periods) - len(cleaned))) + cleaned


def _summarize_financial_rows(periods: list[str], rows: dict[str, dict[str, str]]) -> dict[str, Any]:
    latest = periods[0]
    previous = periods[1] if len(periods) > 1 else None
    revenue_latest = _row_number(rows, "Total Revenue", latest)
    revenue_previous = _row_number(rows, "Total Revenue", previous)
    net_income_latest = _row_number(rows, "Net Income", latest)
    operating_income_latest = _row_number(rows, "Operating Income", latest)
    gross_margin_latest = _row_number(rows, "Gross Margin", latest)
    operating_margin_latest = _row_number(rows, "Operating Margin", latest)
    net_margin_latest = _row_number(rows, "Net Margin", latest)
    eps_latest = _row_number(rows, "EPS (Diluted)", latest)
    price_to_sales = _row_number(rows, "Price To Sales Ratio", latest)
    price_to_earnings = _row_number(rows, "Price To Earnings Ratio", latest)

    revenue_growth = None
    if revenue_previous not in (None, 0) and revenue_latest is not None:
        revenue_growth = ((revenue_latest / revenue_previous) - 1) * 100

    positives = 0
    negatives = 0
    notes: list[str] = []
    if revenue_growth is not None:
        if revenue_growth > 5:
            positives += 1
            notes.append(f"Revenue is growing versus the previous period ({revenue_growth:.1f}%).")
        elif revenue_growth < -5:
            negatives += 1
            notes.append(f"Revenue is shrinking versus the previous period ({revenue_growth:.1f}%).")
    if operating_income_latest is not None:
        positives += int(operating_income_latest > 0)
        negatives += int(operating_income_latest < 0)
    if net_income_latest is not None:
        positives += int(net_income_latest > 0)
        negatives += int(net_income_latest < 0)
    if eps_latest is not None:
        positives += int(eps_latest > 0)
        negatives += int(eps_latest < 0)
    if net_margin_latest is not None and net_margin_latest < 0:
        negatives += 1
        notes.append("Net margin is negative.")
    if price_to_sales is not None and price_to_sales > 10:
        negatives += 1
        notes.append("Price-to-sales is high, so growth quality matters more.")

    if positives > negatives:
        bias = "improving_or_profitable"
    elif negatives > positives:
        bias = "loss_making_or_deteriorating"
    else:
        bias = "mixed"

    return {
        "latest_period": latest,
        "previous_period": previous,
        "bias": bias,
        "revenue": revenue_latest,
        "revenue_growth_pct": None if revenue_growth is None else round(revenue_growth, 2),
        "gross_margin_pct": gross_margin_latest,
        "operating_margin_pct": operating_margin_latest,
        "net_margin_pct": net_margin_latest,
        "operating_income": operating_income_latest,
        "net_income": net_income_latest,
        "eps_diluted": eps_latest,
        "price_to_sales": price_to_sales,
        "price_to_earnings": price_to_earnings,
        "notes": notes,
    }


def _row_number(rows: dict[str, dict[str, str]], label: str, period: Optional[str]) -> Optional[float]:
    if period is None or label not in rows:
        return None
    value = rows[label].get(period)
    if value is None or value in {"-", ""}:
        return None
    try:
        return float(value.replace(",", "").replace("%", ""))
    except ValueError:
        return None


class _SnapshotTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_snapshot_table = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.cells: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and re.search("snapshot-table2", attrs_dict.get("class", "")):
            self.in_snapshot_table = True
        elif self.in_snapshot_table and tag == "td":
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_snapshot_table and tag == "td" and self.in_cell:
            text = " ".join(part.strip() for part in self.current_cell if part.strip())
            self.cells.append(text)
            self.current_cell = []
            self.in_cell = False
        elif self.in_snapshot_table and tag == "table":
            self.in_snapshot_table = False

    def handle_data(self, data: str) -> None:
        if self.in_snapshot_table and self.in_cell:
            self.current_cell.append(data)


class _AllTablesParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.table_depth = 0
        self.in_row = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.current_table: list[list[str]] = []
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "table":
            self.table_depth += 1
            if self.table_depth == 1:
                self.current_table = []
        elif self.table_depth > 0 and tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.table_depth > 0 and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.in_cell:
            text = " ".join(part.strip() for part in self.current_cell if part.strip())
            self.current_row.append(text)
            self.current_cell = []
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if any(self.current_row):
                self.current_table.append(self.current_row)
            self.current_row = []
            self.in_row = False
        elif tag == "table" and self.table_depth > 0:
            if self.table_depth == 1 and self.current_table:
                self.tables.append(self.current_table)
                self.current_table = []
            self.table_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.table_depth > 0 and self.in_cell:
            self.current_cell.append(data)


class _JsonScriptParser(HTMLParser):
    def __init__(self, script_id: str) -> None:
        super().__init__()
        self.script_id = script_id
        self.in_target_script = False
        self.parts: list[str] = []

    @property
    def data(self) -> str:
        return "".join(self.parts).strip()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "script" and attrs_dict.get("id") == self.script_id:
            self.in_target_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_target_script:
            self.in_target_script = False

    def handle_data(self, data: str) -> None:
        if self.in_target_script:
            self.parts.append(data)
