# AGENTS.md

## Project Context

SadQuant is a terminal-first market research CLI for stock, ETF, gold, semiconductor, and index analysis. It is research-only software: it does not place trades and output must not be presented as financial advice.

The active codebase is a Python 3.9+ package under `src/sadquant` with a separate React Ink/TypeScript terminal UI under `ink_tui`. The Python CLI remains the execution engine; the Ink TUI routes slash commands and natural-language input back into the Python CLI.

Core capabilities include:

- Deterministic market snapshots, signal scoring, scans, correlations, insider summaries, and candlestick charts.
- Local SQLite/FTS RAG over ingested notes and provider snippets.
- Optional AI synthesis through Codex CLI, OpenAI, Groq, Gemini, Anthropic, or a generic local CLI adapter.
- Optional data providers for FMP, Funda, Adanos sentiment, Tavily/Brave web search, Finviz, Yahoo/yfinance, and insider activity.
- Structured `research` workflows with tool packets, agentic reports, cited claims, confidence labels, and signal journaling.

## Repository Layout

- `src/sadquant/cli.py`: Typer CLI entrypoint and command wiring.
- `src/sadquant/agent.py`: research agent prompts, structured reports, claim support, and final report rendering.
- `src/sadquant/tools.py`: tool registry and read-only tool adapters used by research.
- `src/sadquant/ai.py`: model/provider clients for OpenAI-compatible APIs, Gemini, Anthropic, Codex CLI, and generic CLI.
- `src/sadquant/market_data.py`, `signals.py`, `universes.py`: yfinance snapshots, scoring, and ticker universe resolution.
- `src/sadquant/rag.py`: local RAG store, chunking, SQLite FTS, deterministic embeddings, and hybrid retrieval helpers.
- `src/sadquant/fmp.py`, `providers.py`, `finviz.py`, `yahoo.py`, `insiders.py`: optional market data providers and normalization.
- `src/sadquant/charts.py`: terminal candlestick chart rendering.
- `src/sadquant/tui*.py`: Python-side TUI launch, command parsing, routing, and bridge logic.
- `ink_tui/src`: Ink/React TUI app, state, keyboard handling, runner, and tests.
- `tests`: Python pytest coverage for CLI helpers, agents, providers, RAG/evals, signals, charts, and TUI routing.
- `docs/AGENT_TOOLS.md`: detailed map of research tools, finance skills, optional provider keys, and suggested agent roles.

## Setup

Use PowerShell commands from the repository root unless noted.

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
cd ink_tui
npm install
npm run build
```

The package exposes the `sadquant` console script from `sadquant.cli:main`.

## Common Commands

```powershell
sadquant analyze NVDA --universe semis
sadquant scan --universe all --top 10
sadquant correlate NVDA AMD --period 1y
sadquant chart NVDA --period 6mo --interval 1d
sadquant insiders NVDA
sadquant ingest-note NVDA "New export controls may affect forward guidance."
sadquant ask NVDA "What are the main risks and catalysts?"
sadquant research NVDA "What setup should I monitor?" --agentic --horizon swing
sadquant tui
```

`analyze`, `scan`, and `correlate` add AI insights by default when an AI provider is available. Use `--no-ai` for deterministic-only output.

## Tests and Verification

Python:

```powershell
python -m pytest
python -m pytest tests\test_agent.py
python -m pytest tests\test_tui_router.py tests\test_tui_commands.py
```

Ink TUI:

```powershell
cd ink_tui
npm run build
npm test
npm run typecheck
```

Prefer focused tests for small changes, and broaden to the full Python or TUI suite when touching shared routing, provider normalization, research reports, RAG, or CLI command behavior.

## Environment

The CLI loads `.env` through `src/sadquant/env.py`. Keep secrets out of commits and use `.env.example` for documented placeholders.

Frequently used variables:

```powershell
$env:SADQUANT_AI_PROVIDER="codex"
$env:SADQUANT_MODEL="gpt-5.5"
$env:OPENAI_API_KEY="..."
$env:GROQ_API_KEY="..."
$env:GEMINI_API_KEY="..."
$env:ANTHROPIC_API_KEY="..."
$env:TAVILY_API_KEY="..."
$env:BRAVE_SEARCH_API_KEY="..."
$env:FMP_API_KEY="..."
$env:FUNDA_API_KEY="..."
$env:ADANOS_API_KEY="..."
```

Provider behavior:

- `codex` uses the official Codex CLI and requires `codex login`.
- `openai`, `groq`, `gemini`, and `anthropic` use direct API keys.
- `cli` sends the tool/RAG packet to `SADQUANT_CLI_COMMAND`.
- `FMP_API_KEY` enables the FMP deep-research tool set automatically in `research`, unless disabled with `--no-fmp`.
- `TAVILY_API_KEY` or `BRAVE_SEARCH_API_KEY` enables live web search.

## Development Guidelines

- Preserve deterministic behavior first. AI synthesis should consume explicit payloads and must not invent prices, fundamentals, catalysts, correlations, or unavailable context.
- Keep provider integrations read-only and fail soft. Missing optional keys should produce clear unavailable/skipped results, not break default Yahoo/yfinance flows.
- Keep terminal output readable both in normal CLI mode and inside the Ink TUI. Be careful with Rich markup, ANSI color, JSON TUI events, and `SADQUANT_TUI_*` environment variables.
- When adding or changing a CLI command, update command metadata and routing in `src/sadquant/tui_commands.py` and `src/sadquant/tui_router.py` if the TUI should expose it.
- When changing chart output, verify both normal terminal rendering and the structured chart event path used by the TUI.
- Use dataclasses and Pydantic-style structured models already present in `src/sadquant/models.py` before adding ad hoc dictionaries for cross-module contracts.
- Prefer bounded, prompt-safe provider payloads. Large tables, news, filings, transcripts, and option chains should be capped and report omitted rows where relevant.
- Keep research language explicit: separate observed data from inference, include data gaps, and end user-facing advice-like output with research-only disclaimers where the surrounding command expects it.
- Do not commit logs, cache directories, virtual environments, local databases, `.env`, or generated build artifacts unless explicitly requested.

## TUI Notes

`sadquant tui` launches `ink_tui/dist/cli.js`. Build the TUI before testing it through the Python CLI.

The TUI sets these environment variables for child CLI calls:

- `SADQUANT_TUI`
- `SADQUANT_TUI_MARKDOWN`
- `SADQUANT_TUI_CHART_MARKUP`
- `SADQUANT_TUI_STATUS_EVENTS`
- `SADQUANT_FORCE_TERMINAL`
- `FORCE_COLOR`

It also removes `NO_COLOR` for child processes so Rich colors and chart colors can render correctly.

Slash-command and free-text behavior lives across both Python and TypeScript:

- Python command parsing/routing: `src/sadquant/tui_commands.py`, `src/sadquant/tui_router.py`, `src/sadquant/tui_bridge.py`.
- TypeScript UI state/runner: `ink_tui/src/state.ts`, `ink_tui/src/runner.ts`, `ink_tui/src/App.tsx`, `ink_tui/src/keyboard.ts`.

## Agent Tool Context

For detailed research-tool behavior and finance-skill routing, read `docs/AGENT_TOOLS.md` before changing agent behavior. Important local research tools include:

- `market_snapshot`
- `yahoo_research`
- `local_rag`
- `hybrid_rag`
- `web_search`
- `sentiment`
- `funda_news`
- `finviz_snapshot`
- `finviz_financials`
- `insider_activity`
- `fmp_market`
- `fmp_fundamentals`
- `fmp_estimates`
- `fmp_catalysts`
- `fmp_transcripts`
- `fmp_insiders`
- `fmp_signal_context`

Treat these as evidence providers. Final research should cite or summarize tool outputs and expose missing data rather than smoothing over gaps.

## Known Local Caveats

- Git may report a dubious-ownership warning inside sandboxed agent sessions for this checkout. Do not run broad Git config changes unless the user asks.
- Network-backed tests and commands may be flaky or require provider keys. Prefer mocking/normalization tests for provider adapters where possible.
- `logs/`, `.pytest_cache/`, `venv/`, `ink_tui/dist/`, and package egg-info are generated/local artifacts.
