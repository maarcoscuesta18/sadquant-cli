from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import json
import os
import sys
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from sadquant.agent import ResearchAgent
from sadquant.ai import ModelError, ModelResponse, create_model
from sadquant.charts import normalize_ohlcv, render_candlestick_chart
from sadquant.cli_logging import configure_cli_logging
from sadquant.env import load_dotenv
from sadquant.evals import load_eval_cases, run_rag_eval, write_eval_report
from sadquant.fmp import ingest_fmp_context
from sadquant.insiders import InsiderDataError, fetch_insider_activity
from sadquant.investor import (
    SCREEN_RECIPES,
    build_setup_plan,
    compare_snapshots,
    fetch_fundamental_snapshot,
    forward_returns_for_signals,
    screen_snapshots,
    summarize_forward_returns,
)
from sadquant.investor_state import InvestorState
from sadquant.journal import SignalJournal
from sadquant.market_data import MarketDataError, correlation, fetch_history, fetch_snapshots
from sadquant.models import RagDocument
from sadquant.output import OutputFormat, emit_structured, to_plain_data
from sadquant.providers import AdanosProvider, FmpProvider, FmpProviderError, FundaProvider
from sadquant.rag import RagStore
from sadquant.signals import score_snapshot
from sadquant.universes import resolve_universe

app = typer.Typer(help="SadQuant: RAG-powered terminal market research.")
eval_app = typer.Typer(help="Evaluate SadQuant retrieval and signal quality.")
signals_app = typer.Typer(help="Save and inspect generated research signals.")
watchlist_app = typer.Typer(help="Create and inspect persistent ticker watchlists.")
thesis_app = typer.Typer(help="Track long-term thesis records and review cadence.")
journal_app = typer.Typer(help="Inspect investor journal statistics.")
app.add_typer(eval_app, name="eval")
app.add_typer(signals_app, name="signals")
app.add_typer(watchlist_app, name="watchlist")
app.add_typer(thesis_app, name="thesis")
app.add_typer(journal_app, name="journal")


def _console_width(default: int = 120) -> int:
    raw = os.getenv("COLUMNS")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(24, value)


console = Console(force_terminal=bool(os.getenv("SADQUANT_FORCE_TERMINAL")), width=_console_width())
load_dotenv()
HORIZONS = {"intraday", "swing", "position"}
FMP_RESEARCH_TOOLS = [
    "fmp_market",
    "fmp_fundamentals",
    "fmp_estimates",
    "fmp_catalysts",
    "fmp_transcripts",
    "fmp_insiders",
    "fmp_signal_context",
]
TUI_EVENT_KEY = "__sadquant_tui_event__"
CLI_INSIGHT_INSTRUCTIONS = """
You are SadQuant's AI insight layer for deterministic CLI outputs.

Use only the supplied command payload. Do not invent prices, correlations,
fundamentals, catalysts, or unavailable context. Clearly separate observed data
from inference. Keep the output concise and terminal-friendly.

For analyze:
- Explain what the score, trend, momentum, risks, RAG context, and co-movers imply.
- Include bullish, bearish, and confidence notes.

For scan:
- Summarize the strongest long/short candidates, breadth of the ranked list, and data gaps.
- Do not imply the scan is a portfolio or trade recommendation.

For correlate:
- Highlight tight pairs, weak diversifiers, cluster risk, and hedging implications.
- Explain when correlation is not causation and where more testing is needed.

End with: Research only. Not financial advice.
"""


@app.callback()
def cli(
    ctx: typer.Context,
    log_dir: Optional[Path] = typer.Option(
        None,
        "--log-dir",
        help="Directory for per-invocation CLI log files. Defaults to ./logs.",
    ),
) -> None:
    """Configure process-wide CLI behavior."""
    configure_cli_logging(log_dir, _current_cli_input(ctx))


def _current_cli_input(ctx: typer.Context) -> list[str]:
    protected_args = [str(arg) for arg in getattr(ctx, "protected_args", [])]
    args = [str(arg) for arg in getattr(ctx, "args", [])]
    if protected_args or args:
        return [*protected_args, *args]
    if ctx.invoked_subcommand:
        return [ctx.invoked_subcommand]
    return _argv_without_log_dir(sys.argv[1:])


def _argv_without_log_dir(argv: list[str]) -> list[str]:
    filtered: list[str] = []
    skip_next = False
    for arg in argv:
        if skip_next:
            skip_next = False
            continue
        if arg == "--log-dir":
            skip_next = True
            continue
        if arg.startswith("--log-dir="):
            continue
        filtered.append(arg)
    return filtered


class _PlainStatus(AbstractContextManager["_PlainStatus"]):
    def __init__(self, message: str) -> None:
        self._message = message

    def __enter__(self) -> "_PlainStatus":
        console.print(f"[cyan]{self._message}[/cyan]")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def update(self, message: str) -> None:
        console.print(message)


class _TuiStatus(AbstractContextManager["_TuiStatus"]):
    def __init__(self, message: str) -> None:
        self._message = message

    def __enter__(self) -> "_TuiStatus":
        _emit_tui_status(self._message)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def update(self, message: str) -> None:
        _emit_tui_status(message)


def _supports_spinner() -> bool:
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf" not in encoding:
        return False
    try:
        "⠧".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _status(message: str):
    if os.getenv("SADQUANT_TUI_STATUS_EVENTS") == "1":
        return _TuiStatus(message)
    if os.getenv("SADQUANT_TUI") == "1":
        return _PlainStatus(message)
    if _supports_spinner():
        return console.status(f"[cyan]{message}[/cyan]", spinner="dots")
    return _PlainStatus(message)


def _print_signal_table(rows: list[tuple[str, str, float, float, float, float, float]]) -> None:
    table = Table(title="SadQuant Signals")
    for column in ["Ticker", "Signal", "Score", "Conf", "Price", "20D %", "RSI"]:
        table.add_column(column, justify="right" if column not in {"Ticker", "Signal"} else "left")
    for ticker, label, score, confidence, price, change_20d, rsi in rows:
        table.add_row(ticker, label, f"{score:.2f}", f"{confidence:.2f}", f"{price:.2f}", f"{change_20d:.1f}", f"{rsi:.1f}")
    console.print(table)


def _maybe_emit_structured(value: Any, output_format: OutputFormat, output: Optional[Path]) -> bool:
    if output_format == "table" and output is None:
        return False
    effective_format = "json" if output_format == "table" else output_format
    emit_structured(value, output_format=effective_format, output=output)
    return True


def _print_dict_table(title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    table = Table(title=title)
    for column in columns:
        table.add_column(column.replace("_", " ").title(), justify="right" if column not in {"ticker", "name", "signal", "recipe", "bias", "risk", "status"} else "left")
    for row in rows:
        table.add_row(*[_format_value(row.get(column)) for column in columns])
    console.print(table)


def _format_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _print_markdown_response(text: str) -> None:
    if os.getenv("SADQUANT_TUI_MARKDOWN") == "1":
        sys.stdout.write(json.dumps({TUI_EVENT_KEY: "markdown", "text": text}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return
    console.print(Markdown(text, code_theme="monokai", hyperlinks=True))


def _emit_tui_status(label: str) -> None:
    clean = str(label).replace("[cyan]", "").replace("[/cyan]", "").strip()
    sys.stdout.write(json.dumps({TUI_EVENT_KEY: "status", "label": clean}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass
    return value


def _build_cli_insight(
    command: str,
    payload: dict[str, Any],
    provider: Optional[str],
    model: Optional[str],
    on_status=None,
) -> ModelResponse:
    client = create_model(provider=provider, model=model)
    if not client.available():
        raise ModelError(f"AI provider '{client.provider}' is not available for CLI insights.")

    prompt = json.dumps(
        {
            "command": command,
            "payload": _json_ready(payload),
        },
        indent=2,
        sort_keys=True,
    )
    return client.complete(prompt, CLI_INSIGHT_INSTRUCTIONS, on_status=on_status)


def _print_cli_insight(response: ModelResponse) -> None:
    console.print(f"\n[bold]AI Insights[/bold] ({response.provider}:{response.model})")
    _print_markdown_response(response.text)


def _print_cli_insight_warning(exc: ModelError) -> None:
    console.print(f"\n[yellow]AI insights skipped:[/yellow] {exc}")


def _validate_horizon(value: str) -> str:
    normalized = value.lower().strip()
    if normalized not in HORIZONS:
        raise typer.BadParameter("horizon must be one of: intraday, swing, position")
    return normalized


@app.command()
def chart(
    ticker: str = typer.Argument(..., help="Ticker to chart."),
    period: str = typer.Option("6mo", help="Yahoo Finance lookback period."),
    interval: str = typer.Option("1d", help="Yahoo Finance interval."),
    height: int = typer.Option(18, help="Price chart height in terminal rows."),
    width: Optional[int] = typer.Option(None, help="Chart width in terminal columns. Defaults to current terminal width."),
    no_volume: bool = typer.Option(False, "--no-volume", help="Hide the volume histogram."),
    plain: bool = typer.Option(False, "--plain", help="Disable Rich color markup."),
) -> None:
    """Draw a terminal candlestick chart for one ticker."""
    symbol = ticker.upper()
    render_width = width if width is not None else console.width
    if render_width < 24:
        raise typer.BadParameter("Terminal is too narrow for a chart. Use a wider terminal or pass a larger --width.")
    if height < 6:
        raise typer.BadParameter("height must be at least 6.")

    with _status(f"Fetching chart data for {symbol}..."):
        data = fetch_history([symbol], period=period, interval=interval)
        candles = normalize_ohlcv(data, symbol)

    try:
        rendered = render_candlestick_chart(
            symbol,
            candles,
            period=period,
            interval=interval,
            height=height,
            width=render_width,
            include_volume=not no_volume,
            plain=plain,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if os.getenv("SADQUANT_TUI_CHART_MARKUP") == "1":
        sys.stdout.write(json.dumps({TUI_EVENT_KEY: "chart", "text": rendered}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    else:
        console.print(rendered)
    console.print("\nResearch output only. No trade execution or financial advice.")


@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="Ticker to analyze."),
    universe: str = typer.Option("all", help="Context universe: etf, gold, semis, indexes, all."),
    period: str = typer.Option("1y", help="Yahoo Finance lookback period."),
    provider: Optional[str] = typer.Option(None, help="AI provider: openai, groq, gemini, anthropic, codex, cli."),
    model: Optional[str] = typer.Option(None, help="Override model name for the selected provider."),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI insight synthesis."),
) -> None:
    """Analyze one ticker with trend, momentum, risk, and local RAG context."""
    linked = None
    with _status(f"Analyzing {ticker.upper()}...") as status:
        store = RagStore()
        status.update(f"[cyan]Loading local context for {ticker.upper()}...[/cyan]")
        context = store.search(ticker, ticker, limit=5)
        status.update(f"[cyan]Fetching market snapshot for {ticker.upper()}...[/cyan]")
        snapshots = fetch_snapshots([ticker.upper()], period=period)
        if not snapshots:
            raise typer.BadParameter(f"No usable market snapshot for {ticker}.")

        snapshot = snapshots[0]
        status.update(f"[cyan]Scoring signal for {ticker.upper()}...[/cyan]")
        signal = score_snapshot(snapshot, context_hits=len(context))

        peers = resolve_universe(universe)
        if ticker.upper() in peers and len(peers) > 1:
            status.update(f"[cyan]Checking {universe} correlations...[/cyan]")
            corr = correlation(peers, period=period)
            if ticker.upper() in corr:
                linked = corr[ticker.upper()].drop(ticker.upper(), errors="ignore").abs().sort_values(ascending=False).head(5)
    _print_signal_table(
        [
            (
                signal.ticker,
                signal.label,
                signal.score,
                signal.confidence,
                snapshot.last_price,
                snapshot.change_20d_pct,
                snapshot.rsi_14,
            )
        ]
    )

    console.print(f"\n[bold]Reasons[/bold]")
    for reason in signal.reasons:
        console.print(f"- {reason}")
    if signal.risks:
        console.print(f"\n[bold]Risks[/bold]")
        for risk in signal.risks:
            console.print(f"- {risk}")

    if context:
        console.print(f"\n[bold]Retrieved Context[/bold]")
        for doc in context:
            console.print(f"- [{doc.source}] {doc.title}: {doc.body[:220]}")

    if linked is not None:
        console.print(f"\n[bold]Closest {universe} co-movers[/bold]")
        for peer, value in linked.items():
            console.print(f"- {peer}: {value:.2f}")

    if not no_ai:
        try:
            with _status(f"Generating AI insights for {ticker.upper()}...") as status:
                response = _build_cli_insight(
                    "analyze",
                    {
                        "ticker": ticker.upper(),
                        "universe": universe,
                        "period": period,
                        "snapshot": snapshot,
                        "signal": signal,
                        "retrieved_context": [
                            {
                                "source": doc.source,
                                "title": doc.title,
                                "created_at": doc.created_at,
                                "body": doc.body[:800],
                            }
                            for doc in context
                        ],
                        "closest_co_movers": None if linked is None else linked.to_dict(),
                    },
                    provider,
                    model,
                    on_status=status.update,
                )
            _print_cli_insight(response)
        except ModelError as exc:
            _print_cli_insight_warning(exc)

    console.print("\nResearch output only. No trade execution or financial advice.")


@app.command()
def scan(
    universe: str = typer.Option("all", help="Universe: etf, gold, semis, indexes, all, or watchlist:<name>."),
    tickers: Optional[list[str]] = typer.Option(None, "--ticker", "-t", help="Add custom tickers."),
    top: int = typer.Option(12, help="Number of rows to show."),
    period: str = typer.Option("1y", help="Yahoo Finance lookback period."),
    provider: Optional[str] = typer.Option(None, help="AI provider: openai, groq, gemini, anthropic, codex, cli."),
    model: Optional[str] = typer.Option(None, help="Override model name for the selected provider."),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI insight synthesis."),
) -> None:
    """Scan a universe and rank long/short research signals."""
    with _status("Preparing scan...") as status:
        status.update(f"[cyan]Resolving {universe} universe...[/cyan]")
        selected = _resolve_investor_tickers(universe, tickers)
        status.update(f"[cyan]Fetching snapshots for {len(selected)} tickers...[/cyan]")
        snapshots = fetch_snapshots(selected, period=period)
        status.update("[cyan]Scoring signals...[/cyan]")
        rows = []
        for snapshot in snapshots:
            signal = score_snapshot(snapshot)
            rows.append((signal, snapshot))

        ranked = sorted(rows, key=lambda item: abs(item[0].score), reverse=True)[:top]
    _print_signal_table(
        [
            (
                signal.ticker,
                signal.label,
                signal.score,
                signal.confidence,
                snapshot.last_price,
                snapshot.change_20d_pct,
                snapshot.rsi_14,
            )
            for signal, snapshot in ranked
        ]
    )
    if not no_ai:
        try:
            with _status("Generating AI insights for scan...") as status:
                response = _build_cli_insight(
                    "scan",
                    {
                        "universe": universe,
                        "requested_tickers": tickers or [],
                        "resolved_ticker_count": len(selected),
                        "returned_snapshot_count": len(snapshots),
                        "period": period,
                        "top": top,
                        "ranked": [
                            {
                                "signal": signal,
                                "snapshot": snapshot,
                            }
                            for signal, snapshot in ranked
                        ],
                    },
                    provider,
                    model,
                    on_status=status.update,
                )
            _print_cli_insight(response)
        except ModelError as exc:
            _print_cli_insight_warning(exc)


@app.command()
def correlate(
    tickers: list[str] = typer.Argument(..., help="Two or more tickers."),
    period: str = typer.Option("1y", help="Yahoo Finance lookback period."),
    provider: Optional[str] = typer.Option(None, help="AI provider: openai, groq, gemini, anthropic, codex, cli."),
    model: Optional[str] = typer.Option(None, help="Override model name for the selected provider."),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI insight synthesis."),
) -> None:
    """Show return correlation matrix for tickers."""
    with _status("Computing correlation matrix..."):
        matrix = correlation([ticker.upper() for ticker in tickers], period=period)
    table = Table(title=f"Correlation Matrix ({period})")
    table.add_column("Ticker")
    for column in matrix.columns:
        table.add_column(str(column), justify="right")
    for idx, row in matrix.iterrows():
        table.add_row(str(idx), *[f"{value:.2f}" for value in row])
    console.print(table)
    if not no_ai:
        try:
            with _status("Generating AI insights for correlation...") as status:
                response = _build_cli_insight(
                    "correlate",
                    {
                        "tickers": [ticker.upper() for ticker in tickers],
                        "period": period,
                        "correlation_matrix": matrix.round(4).to_dict(),
                    },
                    provider,
                    model,
                    on_status=status.update,
                )
            _print_cli_insight(response)
        except ModelError as exc:
            _print_cli_insight_warning(exc)


@app.command()
def insiders(
    ticker: str = typer.Argument(..., help="Ticker to inspect."),
    limit: int = typer.Option(12, help="Recent insider transaction rows to show."),
) -> None:
    """Show what company insiders are buying, selling, and holding."""
    with _status(f"Loading insider activity for {ticker.upper()}..."):
        activity = fetch_insider_activity(ticker, limit=limit)
        summary = activity.summary

    summary_table = Table(title=f"Insider Activity Summary ({activity.ticker})")
    summary_table.add_column("Metric")
    summary_table.add_column("Value", justify="right")
    for key in [
        "bias",
        "buy_shares",
        "sell_shares",
        "net_shares",
        "buy_transactions",
        "sell_transactions",
        "net_transactions",
        "recent_transaction_count",
    ]:
        summary_table.add_row(key.replace("_", " ").title(), _format_value(summary.get(key)))
    console.print(summary_table)

    if activity.recent_transactions:
        tx_table = Table(title="Recent Insider Transactions")
        columns = ["Start Date", "Insider", "Position", "Transaction", "Text", "Shares", "Value", "Ownership"]
        for column in columns:
            tx_table.add_column(column, justify="right" if column in {"Shares", "Value"} else "left")
        for row in activity.recent_transactions:
            tx_table.add_row(*[_format_value(row.get(column)) for column in columns])
        console.print(tx_table)
    else:
        console.print("No recent insider transaction rows returned by Yahoo Finance.")

    if activity.net_purchase_activity:
        net_table = Table(title="Net Purchase Activity")
        columns = list(activity.net_purchase_activity[0].keys())
        for column in columns:
            net_table.add_column(column, justify="right" if column in {"Shares", "Trans"} else "left")
        for row in activity.net_purchase_activity:
            net_table.add_row(*[_format_value(row.get(column)) for column in columns])
        console.print(net_table)


@app.command("ingest-note")
def ingest_note(
    ticker: str = typer.Argument(...),
    body: str = typer.Argument(..., help="Note text to store in local RAG."),
    title: str = typer.Option("Manual note", help="Context title."),
    source: str = typer.Option("manual", help="Context source label."),
) -> None:
    """Add local RAG context for a ticker."""
    with _status(f"Saving note for {ticker.upper()}..."):
        doc = RagDocument(
            ticker=ticker.upper(),
            source=source,
            title=title,
            body=body,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        RagStore().add(doc)
    console.print(f"Stored context for {ticker.upper()} in local RAG database.")


@app.command()
def ask(
    ticker: str = typer.Argument(...),
    question: str = typer.Argument(...),
    limit: int = typer.Option(5, help="Number of context snippets."),
    hybrid: bool = typer.Option(False, "--hybrid", help="Use hybrid label/BM25/vector retrieval."),
    horizon: str = typer.Option("swing", help="Retrieval horizon: intraday, swing, or position."),
) -> None:
    """Retrieve local RAG context for a ticker/question."""
    horizon = _validate_horizon(horizon)
    with _status(f"Searching local context for {ticker.upper()}..."):
        store = RagStore()
        hits = store.hybrid_search(ticker, question, horizon=horizon, limit=limit) if hybrid else []
        docs = [] if hybrid else store.search(ticker, question, limit=limit)
    if hybrid and not hits:
        console.print("No local context found. Add notes with `sadquant ingest-note` or ingest provider context.")
        raise typer.Exit()
    if not hybrid and not docs:
        console.print("No local context found. Add notes with `sadquant ingest-note`.")
        raise typer.Exit()

    console.print(f"[bold]Context for {ticker.upper()}[/bold]")
    if hybrid:
        for hit in hits:
            console.print(
                f"- [{hit.source_id}] {hit.chunk.title} "
                f"(method={hit.method}, fused={hit.fused_score:.4f}, horizon={hit.chunk.labels.get('horizon', 'all')})"
            )
            console.print(f"  {hit.chunk.contextual_text[:500]}")
        return
    for doc in docs:
        console.print(f"- [{doc.source}] {doc.title} ({doc.created_at})")
        console.print(f"  {doc.body[:500]}")


@app.command("ingest-fmp")
def ingest_fmp(
    ticker: str = typer.Argument(..., help="Ticker to ingest from FMP."),
    limit: int = typer.Option(10, help="Maximum news/press release rows to ingest."),
    news: bool = typer.Option(False, "--news", help="Ingest FMP stock news."),
    press_releases: bool = typer.Option(False, "--press-releases", help="Ingest FMP press releases."),
    transcripts: bool = typer.Option(False, "--transcripts", help="Ingest latest FMP earnings transcript context."),
    contextualize: bool = typer.Option(False, "--contextualize", help="Add retrieval context prefixes and chunk metadata."),
) -> None:
    """Store selected FMP long-form context in the local RAG database."""
    if not any([news, press_releases, transcripts]):
        news = True
        press_releases = True
        transcripts = True
    with _status(f"Ingesting FMP context for {ticker.upper()}..."):
        count = ingest_fmp_context(
            ticker,
            include_news=news,
            include_press_releases=press_releases,
            include_transcripts=transcripts,
            limit=limit,
            contextualize=contextualize,
        )
    console.print(f"Stored {count} FMP context document(s) for {ticker.upper()} in local RAG database.")


@app.command()
def research(
    ticker: str = typer.Argument(..., help="Ticker to research."),
    question: str = typer.Argument(..., help="Research question for the agent."),
    web: bool = typer.Option(False, help="Include live web search via Tavily or Brave if configured."),
    sentiment: bool = typer.Option(False, help="Include Adanos sentiment if configured."),
    funda: bool = typer.Option(False, help="Include Funda stock news if configured."),
    finviz: bool = typer.Option(False, help="Include Finviz snapshot plus statement/earnings-style financial rows."),
    insiders: bool = typer.Option(False, help="Include Yahoo Finance insider transactions and net purchase activity."),
    provider: Optional[str] = typer.Option(None, help="AI provider: openai, groq, gemini, anthropic, codex, cli."),
    model: Optional[str] = typer.Option(None, help="Override model name for the selected provider."),
    no_market: bool = typer.Option(False, help="Skip yfinance market snapshot."),
    no_yahoo: bool = typer.Option(False, "--no-yahoo", help="Skip exhaustive Yahoo Finance/yfinance research packet."),
    no_rag: bool = typer.Option(False, help="Skip local RAG retrieval."),
    no_fmp: bool = typer.Option(False, "--no-fmp", help="Disable automatic FMP deep-research tools for this run."),
    agentic: bool = typer.Option(False, "--agentic", help="Use structured multi-agent research workflow."),
    horizon: str = typer.Option("swing", help="Research horizon: intraday, swing, or position."),
    journal_signal: bool = typer.Option(False, "--journal-signal", help="Save the structured signal to the local journal."),
) -> None:
    """Run a tool-backed AI research agent."""
    horizon = _validate_horizon(horizon)
    tools: list[str] = []
    if not no_market:
        tools.append("market_snapshot")
        if not no_yahoo:
            tools.append("yahoo_research")
    if not no_rag:
        tools.append("local_rag")
    if web:
        tools.append("web_search")
    if sentiment:
        tools.append("sentiment")
    if funda:
        tools.append("funda_news")
    if finviz:
        tools.append("finviz_snapshot")
        tools.append("finviz_financials")
    if insiders:
        tools.append("insider_activity")
    if FmpProvider().available() and not no_fmp:
        tools.extend(FMP_RESEARCH_TOOLS)

    def update_status(message: str) -> None:
        status.update(f"[cyan]{message}[/cyan]")

    with _status("Preparing research...") as status:
        agent = ResearchAgent(provider=provider, model_name=model)
        if agentic:
            run = agent.run_agentic(ticker, question, tools, horizon=horizon, on_status=update_status)
        else:
            run = agent.run(ticker, question, tools, on_status=update_status)
    console.print(f"[bold]SadQuant Research Agent[/bold] ({run.response.provider}:{run.response.model})")
    _print_markdown_response(run.response.text)

    if journal_signal and run.report is not None:
        evidence = [
            {
                "claim": claim.text,
                "source_ids": claim.cited_source_ids,
                "support_status": claim.support_status,
            }
            for claim in run.report.claims
        ]
        signal_id = SignalJournal().add(
            ticker=run.report.ticker,
            horizon=run.report.horizon,
            bias=run.report.bias,
            score=run.report.score,
            confidence=run.report.confidence,
            question=question,
            cited_evidence=evidence,
        )
        console.print(f"\n[green]Saved signal journal entry #{signal_id}.[/green]")

    table = Table(title="Tools Used")
    table.add_column("Tool")
    table.add_column("Source")
    for result in run.tools:
        table.add_row(result.name, result.source)
    console.print(table)


@watchlist_app.command("add")
def watchlist_add(
    name: str = typer.Argument(..., help="Watchlist name."),
    tickers: list[str] = typer.Argument(..., help="Tickers to add."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Add tickers to a persistent watchlist."""
    watchlist = InvestorState().add_watchlist_tickers(name, tickers)
    if _maybe_emit_structured(watchlist, output_format, output):
        return
    _print_dict_table("Watchlist", [to_plain_data(watchlist)], ["name", "tickers", "updated_at"])


@watchlist_app.command("remove")
def watchlist_remove(
    name: str = typer.Argument(..., help="Watchlist name."),
    tickers: list[str] = typer.Argument(..., help="Tickers to remove."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Remove tickers from a persistent watchlist."""
    watchlist = InvestorState().remove_watchlist_tickers(name, tickers)
    if _maybe_emit_structured(watchlist, output_format, output):
        return
    _print_dict_table("Watchlist", [to_plain_data(watchlist)], ["name", "tickers", "updated_at"])


@watchlist_app.command("show")
def watchlist_show(
    name: str = typer.Argument("default", help="Watchlist name."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Show one persistent watchlist."""
    watchlist = InvestorState().get_watchlist(name)
    if _maybe_emit_structured(watchlist, output_format, output):
        return
    _print_dict_table("Watchlist", [to_plain_data(watchlist)], ["name", "tickers", "updated_at"])


@watchlist_app.command("list")
def watchlist_list(
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """List persistent watchlists."""
    rows = InvestorState().list_watchlists()
    if _maybe_emit_structured(rows, output_format, output):
        return
    _print_dict_table("Watchlists", [to_plain_data(row) for row in rows], ["name", "tickers", "updated_at"])


@app.command()
def setup(
    ticker: str = typer.Argument(..., help="Ticker to build a deterministic setup plan for."),
    horizon: str = typer.Option("swing", help="Setup horizon: intraday, swing, or position."),
    period: str = typer.Option("1y", help="Yahoo Finance lookback period."),
    journal_signal: bool = typer.Option(False, "--journal-signal", help="Save the setup to the local signal journal."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Build a deterministic swing or position setup brief."""
    horizon = _validate_horizon(horizon)
    with _status(f"Building setup plan for {ticker.upper()}..."):
        plan = build_setup_plan(ticker, horizon=horizon, period=period)
    if journal_signal:
        signal_id = SignalJournal().add(
            ticker=plan.ticker,
            horizon=plan.horizon,
            bias=plan.bias,
            score=plan.signal.score,
            confidence=str(plan.signal.confidence),
            question=f"Deterministic {horizon} setup",
            cited_evidence=[{"claim": reason, "source_ids": ["market_snapshot"], "support_status": "supported"} for reason in plan.signal.reasons],
            entry_price=plan.snapshot.last_price,
            invalidation=plan.invalidation,
            target="; ".join(plan.targets),
        )
    else:
        signal_id = None
    payload = {**to_plain_data(plan), "journal_signal_id": signal_id}
    if _maybe_emit_structured(payload, output_format, output):
        return
    _print_signal_table([(plan.ticker, plan.signal.label, plan.signal.score, plan.signal.confidence, plan.snapshot.last_price, plan.snapshot.change_20d_pct, plan.snapshot.rsi_14)])
    console.print(f"\n[bold]Setup ({plan.horizon})[/bold]")
    console.print(f"- Entry zone: {plan.entry_zone}")
    console.print(f"- Invalidation: {plan.invalidation}")
    for target in plan.targets:
        console.print(f"- Target/watch: {target}")
    console.print("\n[bold]Watch Items[/bold]")
    for item in plan.watch_items:
        console.print(f"- {item}")
    if plan.data_gaps:
        console.print("\n[bold]Data Gaps[/bold]")
        for gap in plan.data_gaps:
            console.print(f"- {gap}")
    if signal_id is not None:
        console.print(f"\n[green]Saved signal journal entry #{signal_id}.[/green]")
    console.print("\nResearch output only. No trade execution or financial advice.")


@app.command()
def compare(
    tickers: list[str] = typer.Argument(..., help="Tickers to compare."),
    period: str = typer.Option("1y", help="Yahoo Finance lookback period."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Compare deterministic signal, momentum, and risk metrics across tickers."""
    if len(tickers) < 2:
        raise typer.BadParameter("compare requires at least two tickers.")
    with _status("Comparing tickers..."):
        snapshots = fetch_snapshots([ticker.upper() for ticker in tickers], period=period)
        rows = compare_snapshots(snapshots)
    if _maybe_emit_structured(rows, output_format, output):
        return
    _print_dict_table(
        f"Compare ({period})",
        rows,
        ["ticker", "signal", "score", "confidence", "price", "change_20d_pct", "change_60d_pct", "rsi_14", "volatility_20d", "risk", "distance_from_52w_high_pct"],
    )


@app.command()
def screen(
    universe: str = typer.Option("all", help="Universe: etf, gold, semis, indexes, all, or watchlist:<name>."),
    tickers: Optional[list[str]] = typer.Option(None, "--ticker", "-t", help="Add custom tickers."),
    recipe: str = typer.Option("momentum", "--recipe", help=f"Screen recipe: {', '.join(sorted(SCREEN_RECIPES))}."),
    top: int = typer.Option(12, help="Number of rows to show."),
    period: str = typer.Option("1y", help="Yahoo Finance lookback period."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Run a named deterministic investor screen."""
    with _status("Running screen..."):
        selected = _resolve_investor_tickers(universe, tickers)
        snapshots = fetch_snapshots(selected, period=period)
        rows = screen_snapshots(snapshots, recipe=recipe)[:top]
    if _maybe_emit_structured(rows, output_format, output):
        return
    _print_dict_table(
        f"Screen: {recipe}",
        [to_plain_data(row) for row in rows],
        ["ticker", "recipe", "score", "signal", "confidence", "price", "change_20d_pct", "change_60d_pct", "rsi_14", "volatility_20d"],
    )


@app.command()
def fundamentals(
    ticker: str = typer.Argument(..., help="Ticker to inspect."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Show deterministic valuation, profitability, growth, and ownership fields."""
    with _status(f"Loading fundamentals for {ticker.upper()}..."):
        snapshot = fetch_fundamental_snapshot(ticker)
    if _maybe_emit_structured(snapshot, output_format, output):
        return
    rows = []
    plain = to_plain_data(snapshot)
    for section in ["valuation", "profitability", "growth", "ownership"]:
        for metric, value in plain[section].items():
            rows.append({"section": section, "metric": metric, "value": value})
    _print_dict_table(f"Fundamentals ({snapshot.ticker})", rows, ["section", "metric", "value"])
    for note in snapshot.notes:
        console.print(f"- {note}")


@app.command()
def earnings(
    ticker: str = typer.Argument(..., help="Ticker to inspect."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Show Yahoo Finance earnings calendar, estimates, and history payloads."""
    from sadquant.yahoo import fetch_yahoo_research

    with _status(f"Loading earnings data for {ticker.upper()}..."):
        payload = fetch_yahoo_research(ticker).get("earnings_events", {})
    result = {"ticker": ticker.upper(), "earnings_events": payload}
    if _maybe_emit_structured(result, output_format, output):
        return
    rows = [{"section": key, "status": value.get("status", "available") if isinstance(value, dict) else "available"} for key, value in payload.items()]
    _print_dict_table(f"Earnings ({ticker.upper()})", rows, ["section", "status"])


@thesis_app.command("add")
def thesis_add(
    ticker: str = typer.Argument(..., help="Ticker."),
    thesis: str = typer.Argument(..., help="Thesis text."),
    horizon: str = typer.Option("position", help="Thesis horizon: intraday, swing, or position."),
    evidence: str = typer.Option("", help="Evidence summary."),
    risks: str = typer.Option("", help="Risk summary."),
    review_date: str = typer.Option("", "--review-date", help="Next review date, e.g. 2026-06-30."),
) -> None:
    """Add a long-term thesis record."""
    horizon = _validate_horizon(horizon)
    thesis_id = InvestorState().add_thesis(ticker=ticker, horizon=horizon, thesis=thesis, evidence=evidence, risks=risks, review_date=review_date)
    console.print(f"Stored thesis #{thesis_id} for {ticker.upper()}.")


@thesis_app.command("list")
def thesis_list(
    ticker: Optional[str] = typer.Option(None, "--ticker", "-t", help="Filter by ticker."),
    status: Optional[str] = typer.Option(None, help="Filter by status."),
    limit: int = typer.Option(50, help="Rows to show."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """List thesis records."""
    rows = InvestorState().list_theses(ticker=ticker, status=status, limit=limit)
    if _maybe_emit_structured(rows, output_format, output):
        return
    _print_dict_table("Theses", [to_plain_data(row) for row in rows], ["id", "ticker", "horizon", "status", "review_date", "thesis"])


@journal_app.command("stats")
def journal_stats(
    horizon: Optional[str] = typer.Option(None, help="Filter by horizon: intraday, swing, or position."),
    limit: int = typer.Option(500, help="Rows to summarize."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Summarize signal journal outcome labels and confidence buckets."""
    if horizon is not None:
        horizon = _validate_horizon(horizon)
    rows = SignalJournal().list(horizon=horizon, limit=limit)
    labeled = [row for row in rows if row.get("outcome_label")]
    wins = [row for row in labeled if str(row.get("outcome_label")).lower() == "win"]
    summary = {
        "signals": len(rows),
        "labeled": len(labeled),
        "win_rate": round(len(wins) / len(labeled), 4) if labeled else None,
        "avg_score": round(sum(float(row["score"]) for row in rows) / len(rows), 4) if rows else None,
    }
    if _maybe_emit_structured(summary, output_format, output):
        return
    _print_dict_table("Journal Stats", [summary], ["signals", "labeled", "win_rate", "avg_score"])


def _resolve_investor_tickers(universe: str, tickers: Optional[list[str]]) -> list[str]:
    if universe.lower().startswith("watchlist:"):
        name = universe.split(":", 1)[1]
        selected = InvestorState().get_watchlist(name).tickers
    else:
        selected = resolve_universe(universe)
    if tickers:
        selected.extend(ticker.upper().strip() for ticker in tickers if ticker.strip())
    return sorted(dict.fromkeys(selected))


@eval_app.command("rag")
def eval_rag(
    dataset: Path = typer.Option(..., "--dataset", help="JSONL eval dataset."),
    report: Optional[Path] = typer.Option(None, "--report", help="Optional JSON report output path."),
    limit: int = typer.Option(8, help="Top-k retrieval depth."),
) -> None:
    """Measure local RAG factual retrieval accuracy with JSONL eval cases."""
    with _status("Running RAG eval..."):
        cases = load_eval_cases(dataset)
        results, summary = run_rag_eval(cases, limit=limit)
        if report is not None:
            write_eval_report(report, results, summary)

    table = Table(title="RAG Eval Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in summary.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)
    if report is not None:
        console.print(f"Report written to {report}")


@eval_app.command("signals")
def eval_signals(
    journal: Optional[Path] = typer.Option(None, "--journal", help="Signal journal SQLite path."),
    horizon: str = typer.Option("swing", help="Signal horizon: intraday, swing, or position."),
) -> None:
    """Summarize labeled signal outcomes. Forward-return scoring is phase two."""
    horizon = _validate_horizon(horizon)
    rows = SignalJournal(journal).list(horizon=horizon, limit=500)
    labeled = [row for row in rows if row.get("outcome_label")]
    table = Table(title=f"Signal Eval ({horizon})")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Signals", str(len(rows)))
    table.add_row("Labeled Outcomes", str(len(labeled)))
    table.add_row("Outcome Coverage", f"{(len(labeled) / len(rows)):.2%}" if rows else "0.00%")
    console.print(table)
    console.print("Forward-return outcome accuracy will use journaled entries once outcome labels are populated.")


@eval_app.command("returns")
def eval_returns(
    journal: Optional[Path] = typer.Option(None, "--journal", help="Signal journal SQLite path."),
    horizon: Optional[str] = typer.Option(None, help="Signal horizon: intraday, swing, or position."),
    limit: int = typer.Option(100, help="Journal rows to evaluate."),
    output_format: OutputFormat = typer.Option("table", "--format", help="Output format: table, json, csv, markdown."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output file path."),
) -> None:
    """Compute forward returns for journaled signals using Yahoo Finance closes."""
    if horizon is not None:
        horizon = _validate_horizon(horizon)
    rows = SignalJournal(journal).list(horizon=horizon, limit=limit)
    with _status("Computing forward returns..."):
        results = forward_returns_for_signals(rows)
        summary = summarize_forward_returns(results)
    payload = {"summary": summary, "results": results}
    if _maybe_emit_structured(payload, output_format, output):
        return
    _print_dict_table("Forward Return Summary", [summary], list(summary.keys()))
    flat_rows = []
    for result in results:
        row = to_plain_data(result)
        returns = row.pop("returns")
        row.update(returns)
        flat_rows.append(row)
    _print_dict_table("Forward Returns", flat_rows, ["signal_id", "ticker", "horizon", "bias", "entry_price", "5d", "20d", "60d", "max_favorable_excursion_pct", "max_adverse_excursion_pct", "outcome"])


@signals_app.command("journal")
def signals_journal(
    horizon: Optional[str] = typer.Option(None, help="Filter by horizon: intraday, swing, or position."),
    limit: int = typer.Option(20, help="Rows to show."),
) -> None:
    """Show saved agentic research signals."""
    if horizon is not None:
        horizon = _validate_horizon(horizon)
    rows = SignalJournal().list(horizon=horizon, limit=limit)
    table = Table(title="Signal Journal")
    for column in ["ID", "Created", "Ticker", "Horizon", "Bias", "Score", "Confidence", "Outcome"]:
        table.add_column(column, justify="right" if column in {"ID", "Score"} else "left")
    for row in rows:
        table.add_row(
            str(row["id"]),
            str(row["created_at"])[:19],
            str(row["ticker"]),
            str(row["horizon"]),
            str(row["bias"]),
            f"{float(row['score']):.2f}",
            str(row["confidence"]),
            str(row.get("outcome_label") or "-"),
        )
    console.print(table)


@signals_app.command("label")
def signals_label(
    signal_id: int = typer.Argument(..., help="Journal signal id."),
    outcome: str = typer.Argument(..., help="Outcome label, e.g. win/loss/neutral/expired."),
    notes: str = typer.Option("", help="Outcome notes."),
) -> None:
    """Attach an outcome label to a journaled signal."""
    SignalJournal().label_outcome(signal_id, label=outcome, notes=notes)
    console.print(f"Updated signal journal entry #{signal_id}.")


@app.command()
def tui() -> None:
    """Open the React Ink slash-command terminal interface."""
    try:
        from sadquant.tui import run_tui
    except ImportError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    try:
        run_tui()
    except ImportError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command()
def providers() -> None:
    """Show optional finance provider availability."""
    with _status("Checking provider availability..."):
        checks = [
            (FmpProvider(), "Financial Modeling Prep deep research data via stable API"),
            (FundaProvider(), "Realtime quotes, fundamentals, filings, options, ETF holdings, macro, news"),
            (AdanosProvider(), "Reddit, X, news, and Polymarket sentiment"),
        ]
        provider_rows = [
            (provider.name, purpose, "available" if provider.available() else f"missing {provider.env_var}")
            for provider, purpose in checks
        ]
        openai_status = "available" if os.getenv("OPENAI_API_KEY") else "missing OPENAI_API_KEY"
        groq_status = "available" if os.getenv("GROQ_API_KEY") else "missing GROQ_API_KEY"
        gemini_status = "available" if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") else "missing GEMINI_API_KEY or GOOGLE_API_KEY"
        anthropic_status = "available" if os.getenv("ANTHROPIC_API_KEY") else "missing ANTHROPIC_API_KEY"
        cli_status = "available" if os.getenv("SADQUANT_CLI_COMMAND") else "missing SADQUANT_CLI_COMMAND"
        web_status = "available" if os.getenv("TAVILY_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY") else "missing TAVILY_API_KEY or BRAVE_SEARCH_API_KEY"
        fmp_base_url = os.getenv("FMP_BASE_URL", FmpProvider.default_base_url)

    table = Table(title="Provider Status")
    table.add_column("Provider")
    table.add_column("Purpose")
    table.add_column("Status")
    for name, purpose, availability in provider_rows:
        table.add_row(name, purpose, availability)
    table.add_row("openai", "AI synthesis through the Responses API", openai_status)
    table.add_row("groq", "AI synthesis through Groq OpenAI-compatible Responses API", groq_status)
    table.add_row("gemini", "AI synthesis through Gemini generateContent", gemini_status)
    table.add_row("anthropic", "AI synthesis through Claude Messages API", anthropic_status)
    table.add_row("codex", "AI synthesis through official Codex CLI auth", "available if `codex` is installed and logged in")
    table.add_row("cli", "AI synthesis through an authenticated local CLI command", cli_status)
    table.add_row("web_search", "Live web search for research agents", web_status)
    table.add_row("fmp_base_url", "FMP base URL override", fmp_base_url)
    console.print(table)


def main() -> None:
    try:
        app()
    except InsiderDataError as exc:
        console.print(f"[red]Insider data error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except MarketDataError as exc:
        console.print(f"[red]Market data error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except FmpProviderError as exc:
        console.print(f"[red]FMP provider error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except ModelError as exc:
        console.print(f"[red]AI model error:[/red] {exc}")
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    main()
