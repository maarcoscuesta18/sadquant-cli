import json
from dataclasses import dataclass

import pandas as pd
from typer.testing import CliRunner
from rich.markdown import Markdown

from sadquant.agent import AGENTIC_INSTRUCTIONS, AGENT_INSTRUCTIONS, ResearchAgent, _strip_inline_source_tags
from sadquant.ai import ModelResponse
from sadquant.cli import CLI_INSIGHT_INSTRUCTIONS, _status, app
from sadquant.cli_logging import configure_cli_logging
from sadquant.models import MarketSnapshot
from sadquant.tools import ToolRegistry, ToolResult


@dataclass
class FakeModel:
    provider: str = "fake-provider"
    model: str = "fake-model"

    def available(self) -> bool:
        return True

    def complete(self, prompt: str, instructions: str, on_status=None):
        if on_status is not None:
            on_status(f"Calling {self.provider}:{self.model}")
        assert instructions == AGENT_INSTRUCTIONS
        assert "## Tool: market_snapshot" in prompt
        return type("Response", (), {"provider": self.provider, "model": self.model, "text": "done"})()


@dataclass
class FakeUnavailableModel:
    provider: str = "fake-provider"
    model: str = "fake-model"

    def available(self) -> bool:
        return False


def test_research_instructions_require_traders_plan():
    for expected in [
        "Trader's Plan",
        "Recommendation",
        "Entry Plan",
        "Stop / Invalidation",
        "Final Decision",
    ]:
        assert expected in AGENT_INSTRUCTIONS


def test_agentic_instructions_require_traders_plan():
    assert "Trader's Plan" in AGENTIC_INSTRUCTIONS
    assert "Recommendation: BUY, SELL/SHORT, HOLD/WATCH, or NO TRADE" in AGENTIC_INSTRUCTIONS
    assert "Final Decision" in AGENTIC_INSTRUCTIONS


def test_tui_status_emits_structured_status_event(monkeypatch, capsys):
    monkeypatch.setenv("SADQUANT_TUI", "1")
    monkeypatch.setenv("SADQUANT_TUI_STATUS_EVENTS", "1")

    with _status("Preparing research...") as status:
        status.update("[cyan]Calling fake-provider:fake-model[/cyan]")

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines == [
        {"__sadquant_tui_event__": "status", "label": "Preparing research..."},
        {"__sadquant_tui_event__": "status", "label": "Calling fake-provider:fake-model"},
    ]


def test_tui_status_without_capability_uses_plain_text(monkeypatch, capsys):
    monkeypatch.setenv("SADQUANT_TUI", "1")
    monkeypatch.delenv("SADQUANT_TUI_STATUS_EVENTS", raising=False)

    with _status("Preparing research...") as status:
        status.update("[cyan]Calling fake-provider:fake-model[/cyan]")

    output = capsys.readouterr().out
    assert "__sadquant_tui_event__" not in output
    assert "Calling fake-provider:fake-model" in output


def test_research_agent_emits_progress_updates():
    registry = ToolRegistry()
    registry.register("market_snapshot", lambda ticker, query: ToolResult(name="market_snapshot", source="test", data={"ticker": ticker}))
    messages: list[str] = []

    run = ResearchAgent(model=FakeModel(), registry=registry).run(
        "NVDA",
        "What matters here?",
        ["market_snapshot"],
        on_status=messages.append,
    )

    assert run.response.text == "done"
    assert messages == [
        "Running market snapshot...",
        "Synthesizing answer with fake-provider...",
        "Calling fake-provider:fake-model",
    ]


def test_inline_tool_source_tags_are_stripped_from_response():
    result = ToolResult(name="market_snapshot", source="yfinance", data={"ticker": "NVDA"})
    text = (
        "- Recommendation: NO TRADE. [market_snapshot][yahoo_research]\n"
        "- Keep normal bracketed prose [watchlist] untouched.\n"
        "- Retrieved note was checked. [NVDA:manual:1:1]"
    )

    cleaned = _strip_inline_source_tags(text, [result])

    assert "[market_snapshot]" not in cleaned
    assert "[yahoo_research]" not in cleaned
    assert "[NVDA:manual:1:1]" not in cleaned
    assert "[watchlist]" in cleaned


def test_research_agent_logs_tool_failures(tmp_path):
    log_file = configure_cli_logging(tmp_path, ["research", "NVDA", "What changed?", "--finviz"])
    registry = ToolRegistry()

    def fail_tool(ticker, query):
        raise RuntimeError("simulated provider failure")

    registry.register("fmp_market", fail_tool)

    run = ResearchAgent(model=FakeUnavailableModel(), registry=registry).run(
        "NVDA",
        "What changed?",
        ["fmp_market"],
    )

    assert run.tools[0].source == "tool-error"
    assert run.tools[0].data["error_type"] == "RuntimeError"
    assert run.tools[0].data["log_file"] == str(log_file)
    log_text = log_file.read_text(encoding="utf-8")
    assert "Tool failed: name=fmp_market ticker=NVDA" in log_text
    assert "simulated provider failure" in log_text


def test_cli_logging_uses_cli_input_for_log_file(tmp_path):
    research_log = configure_cli_logging(tmp_path, ["research", "NVDA", "What changed?", "--finviz"])
    scan_log = configure_cli_logging(tmp_path, ["scan", "--universe", "semis"])

    assert research_log.name.startswith("sadquant-research-nvda-what-changed-finviz-")
    assert scan_log.name.startswith("sadquant-scan-universe-semis-")
    assert research_log.name.endswith(".log")
    assert scan_log.name.endswith(".log")
    assert research_log != scan_log


def test_agentic_research_builds_structured_report():
    registry = ToolRegistry()
    registry.register(
        "hybrid_rag",
        lambda ticker, query: ToolResult(
            name="hybrid_rag",
            source="sqlite-hybrid-bm25-vector",
            data={
                "matches": [
                    {
                        "source_id": "NVDA:manual:1:1",
                        "title": "Guidance note",
                        "contextual_text": "NVDA guidance improved for data center demand.",
                    }
                ]
            },
        ),
    )
    registry.register(
        "market_snapshot",
        lambda ticker, query: ToolResult(
            name="market_snapshot",
            source="yfinance",
            data={
                "ticker": ticker,
                "last_price": 100.0,
                "change_20d_pct": 5.0,
                "rsi_14": 61.0,
                "signal": "LONG_BIAS",
                "score": 2.0,
            },
        ),
    )

    run = ResearchAgent(model=FakeUnavailableModel(), registry=registry).run_agentic(
        "NVDA",
        "What changed?",
        ["market_snapshot", "local_rag"],
        horizon="swing",
    )

    assert run.report is not None
    assert run.report.horizon == "swing"
    assert run.report.bias == "LONG_BIAS"
    assert "Verifier" in run.response.text
    assert "## Trader's Plan" in run.response.text
    assert "- Recommendation:" in run.response.text
    assert "- Entry Plan:" in run.response.text
    assert "- Stop / Invalidation:" in run.response.text
    assert run.response.text.index("## Trader's Plan") < run.response.text.index("Research only. Not financial advice.")


def test_research_command_shows_status_updates(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    captured_statuses: list[str] = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            captured_statuses.append(message)

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)

    class FakeAgent:
        def __init__(self, provider=None, model_name=None):
            self.provider = provider
            self.model_name = model_name

        def run(self, ticker, question, tools, on_status=None):
            if on_status is not None:
                on_status("Running market snapshot...")
                on_status("Synthesizing answer with codex...")
            response = type("Response", (), {"provider": "codex", "model": "codex-cli", "text": "result"})()
            return type("Run", (), {"response": response, "tools": []})()

    monkeypatch.setattr("sadquant.cli.ResearchAgent", FakeAgent)

    result = CliRunner().invoke(app, ["research", "NVDA", "What changed?"])

    assert result.exit_code == 0
    assert captured_statuses == [
        "[cyan]Running market snapshot...[/cyan]",
        "[cyan]Synthesizing answer with codex...[/cyan]",
    ]


def test_research_command_renders_response_as_markdown(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    rendered = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            pass

    def fake_print(*args, **kwargs):
        rendered.extend(args)

    class FakeAgent:
        def __init__(self, provider=None, model_name=None):
            pass

        def run(self, ticker, question, tools, on_status=None):
            response = type("Response", (), {"provider": "codex", "model": "codex-cli", "text": "## Take\n\n- **Bias:** watch"})()
            return type("Run", (), {"response": response, "tools": []})()

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", fake_print)
    monkeypatch.setattr("sadquant.cli.ResearchAgent", FakeAgent)

    result = CliRunner().invoke(app, ["research", "NVDA", "What changed?", "--no-fmp"])

    assert result.exit_code == 0
    markdown_outputs = [item for item in rendered if isinstance(item, Markdown)]
    assert len(markdown_outputs) == 1
    assert markdown_outputs[0].markup == "## Take\n\n- **Bias:** watch"


def test_scan_command_generates_ai_insights(monkeypatch):
    captured = {}
    status_messages: list[str] = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            status_messages.append(message)

    class FakeModelClient:
        provider = "fake-provider"

        def __init__(self):
            self.model = "fake-model"

        def available(self):
            return True

        def complete(self, prompt, instructions, on_status=None):
            captured["prompt"] = prompt
            captured["instructions"] = instructions
            if on_status is not None:
                on_status(f"Calling {self.provider}:{self.model}")
            return ModelResponse(provider=self.provider, model=self.model, text="## Scan\n\n- insight")

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("sadquant.cli.resolve_universe", lambda universe, tickers=None: ["NVDA"])
    monkeypatch.setattr(
        "sadquant.cli.fetch_snapshots",
        lambda tickers, period="1y": [
            MarketSnapshot(
                ticker="NVDA",
                last_price=100.0,
                change_20d_pct=8.0,
                change_60d_pct=20.0,
                rsi_14=62.0,
                sma_20=95.0,
                sma_50=90.0,
                sma_200=80.0,
                volatility_20d=30.0,
                high_52w=110.0,
                low_52w=60.0,
                observations=252,
            )
        ],
    )
    monkeypatch.setattr("sadquant.cli.create_model", lambda provider=None, model=None: FakeModelClient())

    result = CliRunner().invoke(app, ["scan", "--universe", "semis", "--top", "1"])

    assert result.exit_code == 0
    assert captured["instructions"] == CLI_INSIGHT_INSTRUCTIONS
    assert '"command": "scan"' in captured["prompt"]
    assert '"ticker": "NVDA"' in captured["prompt"]
    assert "Calling fake-provider:fake-model" in status_messages


def test_correlate_no_ai_skips_model(monkeypatch):
    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            pass

    def fail_create_model(provider=None, model=None):
        raise AssertionError("model should not be created when --no-ai is set")

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "sadquant.cli.correlation",
        lambda tickers, period="1y": pd.DataFrame(
            [[1.0, 0.5], [0.5, 1.0]],
            index=["NVDA", "AMD"],
            columns=["NVDA", "AMD"],
        ),
    )
    monkeypatch.setattr("sadquant.cli.create_model", fail_create_model)

    result = CliRunner().invoke(app, ["correlate", "NVDA", "AMD", "--no-ai"])

    assert result.exit_code == 0


def test_providers_command_shows_status_updates(monkeypatch):
    captured_statuses: list[str] = []
    created_messages: list[str] = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            captured_statuses.append(message)

    def fake_status(message, **kwargs):
        created_messages.append(message)
        return FakeStatus()

    monkeypatch.setattr("sadquant.cli.console.status", fake_status)
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)

    result = CliRunner().invoke(app, ["providers"])

    assert result.exit_code == 0
    assert created_messages == ["[cyan]Checking provider availability...[/cyan]"]
    assert captured_statuses == []


def test_ask_command_shows_status_updates(monkeypatch):
    captured_statuses: list[str] = []
    created_messages: list[str] = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            captured_statuses.append(message)

    class FakeStore:
        def search(self, ticker, question, limit=5):
            return [type("Doc", (), {"source": "manual", "title": "Note", "created_at": "2026-01-01", "body": "Body"})()]

    def fake_status(message, **kwargs):
        created_messages.append(message)
        return FakeStatus()

    monkeypatch.setattr("sadquant.cli.console.status", fake_status)
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("sadquant.cli.RagStore", lambda: FakeStore())

    result = CliRunner().invoke(app, ["ask", "NVDA", "What changed?"])

    assert result.exit_code == 0
    assert created_messages == ["[cyan]Searching local context for NVDA...[/cyan]"]
    assert captured_statuses == []


def test_research_command_auto_adds_fmp_tools_when_key_is_set(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    captured_tools = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            pass

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)

    class FakeAgent:
        def __init__(self, provider=None, model_name=None):
            pass

        def run(self, ticker, question, tools, on_status=None):
            captured_tools.extend(tools)
            response = type("Response", (), {"provider": "codex", "model": "codex-cli", "text": "result"})()
            return type("Run", (), {"response": response, "tools": []})()

    monkeypatch.setattr("sadquant.cli.ResearchAgent", FakeAgent)

    result = CliRunner().invoke(app, ["research", "NVDA", "What changed?"])

    assert result.exit_code == 0
    assert "fmp_market" in captured_tools
    assert "fmp_signal_context" in captured_tools


def test_research_command_no_fmp_suppresses_auto_tools(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    captured_tools = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            pass

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)

    class FakeAgent:
        def __init__(self, provider=None, model_name=None):
            pass

        def run(self, ticker, question, tools, on_status=None):
            captured_tools.extend(tools)
            response = type("Response", (), {"provider": "codex", "model": "codex-cli", "text": "result"})()
            return type("Run", (), {"response": response, "tools": []})()

    monkeypatch.setattr("sadquant.cli.ResearchAgent", FakeAgent)

    result = CliRunner().invoke(app, ["research", "NVDA", "What changed?", "--no-fmp"])

    assert result.exit_code == 0
    assert "market_snapshot" in captured_tools
    assert "yahoo_research" in captured_tools
    assert "fmp_market" not in captured_tools


def test_research_command_no_yahoo_suppresses_yahoo_packet(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    captured_tools = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            pass

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)

    class FakeAgent:
        def __init__(self, provider=None, model_name=None):
            pass

        def run(self, ticker, question, tools, on_status=None):
            captured_tools.extend(tools)
            response = type("Response", (), {"provider": "codex", "model": "codex-cli", "text": "result"})()
            return type("Run", (), {"response": response, "tools": []})()

    monkeypatch.setattr("sadquant.cli.ResearchAgent", FakeAgent)

    result = CliRunner().invoke(app, ["research", "NVDA", "What changed?", "--no-yahoo"])

    assert result.exit_code == 0
    assert "market_snapshot" in captured_tools
    assert "yahoo_research" not in captured_tools


def test_research_command_agentic_passes_horizon(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    captured = {}

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, message: str) -> None:
            pass

    class FakeAgent:
        def __init__(self, provider=None, model_name=None):
            pass

        def run_agentic(self, ticker, question, tools, horizon, on_status=None):
            captured["horizon"] = horizon
            response = type("Response", (), {"provider": "local", "model": "rules", "text": "agentic"})()
            return type("Run", (), {"response": response, "tools": [], "report": None})()

    monkeypatch.setattr("sadquant.cli.console.status", lambda *args, **kwargs: FakeStatus())
    monkeypatch.setattr("sadquant.cli.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("sadquant.cli.ResearchAgent", FakeAgent)

    result = CliRunner().invoke(app, ["research", "NVDA", "What changed?", "--agentic", "--horizon", "position", "--no-fmp"])

    assert result.exit_code == 0
    assert captured["horizon"] == "position"
