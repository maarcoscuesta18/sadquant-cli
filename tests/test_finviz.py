from sadquant.finviz import FinvizError, fetch_finviz_financials, _parse_financial_statement, _parse_snapshot_cells
from sadquant.tools import finviz_financials_tool


def test_parse_finviz_snapshot_cells():
    html = """
    <table class="snapshot-table2">
      <tr>
        <td>Market Cap</td><td>3153.07B</td>
        <td>P/E</td><td>26.57</td>
        <td>EPS next Y</td><td>14.64%</td>
      </tr>
      <tr>
        <td>RSI (14)</td><td>63.46</td>
        <td>Target Price</td><td>573.51</td>
      </tr>
    </table>
    """

    metrics = _parse_snapshot_cells(html)

    assert metrics["Market Cap"] == "3153.07B"
    assert metrics["P/E"] == "26.57"
    assert metrics["EPS next Y"] == "14.64%"
    assert metrics["RSI (14)"] == "63.46"
    assert metrics["Target Price"] == "573.51"


def test_parse_financial_statement_rows_and_summary():
    html = """
    <table>
      <tr><td>Period</td><td></td><td>TTM</td><td>FY 2025</td><td>FY 2024</td></tr>
      <tr><td>Period End Date</td><td></td><td>-</td><td>6/30/2025</td><td>6/30/2024</td></tr>
      <tr><td>Total Revenue</td><td></td><td>8,929.00</td><td>7,355.00</td><td>6,663.00</td></tr>
      <tr><td>Gross Profit</td><td></td><td>3,108.00</td><td>2,212.00</td><td>1,072.00</td></tr>
      <tr><td>Operating Income</td><td></td><td>1,276.00</td><td>507.00</td><td>-444.00</td></tr>
      <tr><td>Net Income</td><td></td><td>-1,041.00</td><td>-1,641.00</td><td>-672.00</td></tr>
      <tr><td>EPS (Diluted)</td><td></td><td>-7.59</td><td>-11.24</td><td>-4.63</td></tr>
      <tr><td>Price To Sales Ratio</td><td></td><td>4.81</td><td>0.94</td><td>-</td></tr>
      <tr><td>Gross Margin</td><td></td><td>34.81</td><td>30.07</td><td>16.09</td></tr>
      <tr><td>Operating Margin</td><td></td><td>14.29</td><td>6.89</td><td>-6.66</td></tr>
      <tr><td>Net Margin</td><td></td><td>-11.66</td><td>-22.31</td><td>-10.09</td></tr>
    </table>
    """

    financials = _parse_financial_statement(html)

    assert financials["periods"] == ["TTM", "FY 2025", "FY 2024"]
    assert financials["rows"]["Total Revenue"]["TTM"] == "8,929.00"
    assert financials["rows"]["Operating Margin"]["FY 2024"] == "-6.66"
    assert financials["summary"]["latest_period"] == "TTM"
    assert financials["summary"]["revenue"] == 8929.0
    assert financials["summary"]["revenue_growth_pct"] == 21.4
    assert financials["summary"]["operating_margin_pct"] == 14.29
    assert financials["summary"]["net_margin_pct"] == -11.66
    assert financials["summary"]["bias"] == "loss_making_or_deteriorating"


def test_parse_financial_analysis_json_when_statement_table_is_absent():
    html = """
    <html>
      <script id="fa-init-data-0" type="application/json">
        {
          "annual": {
            "values": [
              [{"name":"2023","value":-14.779},{"name":"2024","value":-4.635},{"name":"2025","value":-11.24},{"name":"TTM","value":-7.5894}],
              [{"name":"2023","value":6086},{"name":"2024","value":6663},{"name":"2025","value":7355},{"name":"TTM","value":8929}],
              [{"name":"2023","value":145},{"name":"2024","value":145},{"name":"2025","value":146}]
            ]
          },
          "quarterly": {
            "values": [
              [{"name":"Q1 '26","value":0.752},{"name":"Q2 '26","value":5.147}],
              [{"name":"Q1 '26","value":2308},{"name":"Q2 '26","value":3025}],
              [{"name":"Q1 '26","value":147},{"name":"Q2 '26","value":148}]
            ]
          }
        }
      </script>
    </html>
    """

    financials = _parse_financial_statement(html)

    assert financials["periods"] == ["TTM", "FY 2025", "FY 2024", "FY 2023"]
    assert financials["rows"]["Total Revenue"]["TTM"] == "8,929"
    assert financials["rows"]["EPS (Diluted)"]["FY 2025"] == "-11.24"
    assert financials["quarterly_periods"] == ["Q2 '26", "Q1 '26"]
    assert financials["quarterly_rows"]["Total Revenue"]["Q2 '26"] == "3,025"
    assert financials["summary"]["latest_period"] == "TTM"
    assert financials["summary"]["revenue"] == 8929.0
    assert financials["summary"]["revenue_growth_pct"] == 21.4
    assert financials["summary"]["bias"] == "mixed"


def test_fetch_finviz_financials_uses_earnings_analysis_tab(monkeypatch):
    captured = {}

    def fake_fetch_quote_page(ticker, quote_type=None):
        captured["ticker"] = ticker
        captured["quote_type"] = quote_type
        return """
        <script id="fa-init-data-0" type="application/json">
          {"annual":{"values":[[{"name":"TTM","value":1.5}],[{"name":"TTM","value":100}],[{"name":"TTM","value":10}]]}}
        </script>
        """

    monkeypatch.setattr("sadquant.finviz._fetch_quote_page", fake_fetch_quote_page)

    result = fetch_finviz_financials("SNDK")

    assert captured == {"ticker": "SNDK", "quote_type": "ea"}
    assert result["ticker"] == "SNDK"
    assert result["rows"]["Total Revenue"]["TTM"] == "100"


def test_finviz_financials_tool_returns_unavailable_on_parse_error(monkeypatch):
    def fail_fetch(ticker):
        raise FinvizError(f"Could not parse Finviz financial statement for {ticker}.")

    monkeypatch.setattr("sadquant.tools.fetch_finviz_financials", fail_fetch)

    result = finviz_financials_tool("SNDK", "What is the setup?")

    assert result.source == "finviz-unavailable"
    assert result.data["ticker"] == "SNDK"
    assert result.data["error_type"] == "FinvizError"
    assert result.data["summary"]["bias"] == "unavailable"
