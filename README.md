# SadQuant

SadQuant is a terminal-first research CLI for stock, ETF, gold, semiconductor, and index analysis. It combines market data, local RAG context, optional sentiment/fundamental providers, and deterministic signal scoring for long/short research.

It does not place trades and should not be treated as financial advice.

<img width="1233" height="897" alt="image" src="https://github.com/user-attachments/assets/2f027641-5607-4b83-91ac-ff90b1206cd6" />

## Install

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
cd ink_tui
npm install
npm run build
```

## Quick Start

```powershell
sadquant analyze NVDA --universe semis
sadquant tui
sadquant chart NVDA --period 6mo --interval 1d
sadquant scan --universe all --top 10
sadquant screen --universe semis --recipe momentum --top 10
sadquant setup NVDA --horizon swing --journal-signal
sadquant compare NVDA AMD AVGO
sadquant fundamentals NVDA
sadquant earnings NVDA
sadquant watchlist add semis NVDA AMD AVGO
sadquant thesis add NVDA "AI data center demand remains durable." --horizon position
sadquant journal stats --horizon swing
sadquant eval returns --horizon swing
sadquant correlate NVDA AMD --period 1y
sadquant ingest-note NVDA "New export controls may affect forward guidance."
sadquant ask NVDA "What are the main risks and catalysts?"
sadquant insiders NVDA
sadquant research NVDA "Should I watch for a long or short setup this week?" --web --sentiment --finviz --insiders
sadquant research NVDA "What is the setup?" --agentic --horizon swing --journal-signal
sadquant eval rag --dataset evals/rag.jsonl --report reports/rag-eval.json
```

`analyze`, `scan`, and `correlate` now add AI insights by default using `SADQUANT_AI_PROVIDER` / `SADQUANT_MODEL`, or command-level `--provider` / `--model` overrides. Use `--no-ai` when you only want the deterministic tables.

## Interactive TUI

SadQuant also includes an opt-in Claude/Codex/OpenCode-style terminal interface built with React Ink:

```powershell
sadquant tui
```

The TUI runs inline and keeps the existing SadQuant CLI as its execution engine. Inside the TUI, existing CLI commands are available as one-shot slash commands:

```text
what changed for NVDA today?
chart NVDA 6mo
compare NVDA vs AMD
```

<img width="1237" height="849" alt="image" src="https://github.com/user-attachments/assets/43690d41-227f-4294-b63e-ef4ad6f097ee" />


Root-prompt free text is routed automatically to the best existing SadQuant CLI command. Obvious requests use deterministic rules, ambiguous natural-language requests use the configured AI provider as an intent router, and the resulting command is validated before it can run.

```text
/research NVDA "What changed?" --web --finviz
/analyze NVDA --universe semis
/chart NVDA --period 6mo
/scan --universe all --top 10
/eval rag --dataset evals/rag.jsonl
/signals journal --horizon swing
```

Bare slash commands enter persistent command modes:

```text
/chart
NVDA --period 6mo --interval 1d
/mode off
```

In `chart>` mode, each line is executed as `sadquant chart ...`. The same mode pattern works for commands such as `/research`, `/analyze`, `/scan`, `/ask`, `/eval`, and `/signals`. Slash commands with arguments remain one-shot commands and do not enter mode.

Autocomplete is keyboard-first: type `/` or a partial command such as `/re` to see matching slash commands, use Up/Down to move through suggestions, and press Enter to complete the current token before submitting. Tab accepts the highlighted suggestion even after a trailing space, which is useful for templates and argument prompts. In command modes, autocomplete suggests known options and no-dash aliases, so `chart> NVDA period 6mo interval 1d` compiles to the same CLI call as `NVDA --period 6mo --interval 1d`. Press Ctrl+O in a command mode to open the option editor, use arrows to move, Space to toggle booleans, Left/Right to cycle choices, and Enter to apply. Ctrl+U clears before the cursor, Ctrl+K clears after it, Ctrl+W deletes the previous word, and Ctrl+L clears the transcript. Press Ctrl+C while a command is running to interrupt it; press Ctrl+C while idle to exit.

Use `/plan` to toggle plan mode. In plan mode, slash commands and active-mode input are parsed and shown as planned actions instead of executing immediately. Use `/run` to execute the latest planned command, `/plan off` to return to normal mode, `/exit-mode` or Esc to leave an active command mode, `/clear` to clear the transcript, and `/exit` to leave the TUI.

The TUI sets `SADQUANT_TUI`, `SADQUANT_TUI_MARKDOWN`, `SADQUANT_TUI_CHART_MARKUP`, `SADQUANT_TUI_STATUS_EVENTS`, `SADQUANT_FORCE_TERMINAL`, and `FORCE_COLOR` for child CLI calls. That keeps status updates, Markdown answers, ANSI-colored output, and candlestick chart markup readable inside Ink while preserving normal CLI behavior outside the TUI. `NO_COLOR` is removed for TUI child processes so chart output and Rich colors can render correctly.

Chart commands now keep their normal colored rendering path in the TUI. When `SADQUANT_TUI_CHART_MARKUP=1`, the Python CLI emits a structured chart event, the TypeScript runner parses it, and the Ink app converts Rich-style `[green]`, `[red]`, and `[cyan]` chart markup into ANSI-colored `Text` segments.

## Optional Provider Keys

The CLI works with Yahoo Finance by default through `yfinance`.

Optional richer data sources:

```powershell
$env:SADQUANT_AI_PROVIDER="codex"
$env:SADQUANT_MODEL="gpt-5.5"
$env:FMP_API_KEY="..."
$env:FUNDA_API_KEY="..."
$env:ADANOS_API_KEY="..."
$env:OPENAI_API_KEY="..."
$env:GROQ_API_KEY="..."
$env:SADQUANT_GROQ_MODEL="openai/gpt-oss-20b"
$env:GEMINI_API_KEY="..."
$env:SADQUANT_GEMINI_MODEL="gemini-2.5-pro"
$env:ANTHROPIC_API_KEY="..."
$env:SADQUANT_ANTHROPIC_MODEL="claude-sonnet-4-20250514"
$env:TAVILY_API_KEY="..."
# or
$env:BRAVE_SEARCH_API_KEY="..."
```

`FUNDA_API_KEY` enables Funda AI endpoints for quotes, fundamentals, options flow, filings, transcripts, ETF holdings, macro data, and news.

`FMP_API_KEY` enables Financial Modeling Prep deep-research tools automatically in `sadquant research`, including quote/history, fundamentals, analyst estimates, news, press releases, transcripts, insider statistics, and deterministic signal context. Override the base URL with `FMP_BASE_URL` if needed.

`ADANOS_API_KEY` enables structured Reddit, X, news, and Polymarket sentiment snapshots.

By default, SadQuant uses the official Codex CLI provider. Run `codex login` first so Codex can use your ChatGPT subscription auth.

`OPENAI_API_KEY` enables direct OpenAI API synthesis through the OpenAI Responses API. Without direct API keys, use the default `codex` provider.

`GROQ_API_KEY`, `GEMINI_API_KEY`, and `ANTHROPIC_API_KEY` enable alternate AI providers.

`TAVILY_API_KEY` or `BRAVE_SEARCH_API_KEY` enables live web search for the research agent.

## Agent Tools

The `research` command gives the AI model explicit read-only tool outputs:

- `market_snapshot`: yfinance price, momentum, volatility, and deterministic signal score.
- `yahoo_research`: exhaustive public Yahoo Finance/yfinance research packet with price/history metadata, financial statements, estimates, analyst data, holders, insider rows, filings/events, options, sustainability, fund data, and news. Large tables, news, and option chains are capped and report omitted rows.
- `local_rag`: local SQLite FTS notes and ingested snippets.
- `hybrid_rag`: local contextual retrieval with labels, BM25/FTS, deterministic vector search, rank fusion, and source ids.
- `web_search`: Tavily or Brave web search results.
- `sentiment`: Adanos structured sentiment when `ADANOS_API_KEY` is set.
- `funda_news`: Funda stock news when `FUNDA_API_KEY` is set.
- `finviz_snapshot`: Finviz quote-page valuation, growth, profitability, ownership, performance, technical, and volume metrics.
- `finviz_financials`: Finviz quote-page financial statement rows such as revenue, operating income, net income, EPS, margins, and price-to-sales/earnings ratios.
- `insider_activity`: yfinance insider transactions, net purchase/sale activity, and insider roster rows.
- `fmp_market`: Financial Modeling Prep quote, historical EOD, RSI, and price change.
- `fmp_fundamentals`: FMP profile, peers, statements, and key metrics.
- `fmp_estimates`: FMP analyst estimates, ratings snapshot, and price target consensus.
- `fmp_catalysts`: FMP stock news and press releases.
- `fmp_transcripts`: FMP latest earnings transcript metadata and selected transcript content.
- `fmp_insiders`: FMP insider trading statistics.
- `fmp_signal_context`: deterministic combined signal context from yfinance plus FMP quality, valuation, analyst, catalyst, and insider evidence.

Default run:

```powershell
sadquant research NVDA "What setup should I monitor?"
```

By default, `research` includes both the lightweight deterministic `market_snapshot` and the broader `yahoo_research` packet. Use `--no-yahoo` to skip the exhaustive Yahoo packet while keeping the market snapshot, or `--no-market` to skip both yfinance market tools.

Provider-specific runs:

```powershell
sadquant analyze NVDA --universe semis --provider codex --model gpt-5.5
sadquant scan --universe semis --top 10 --provider openai --model gpt-5.5
sadquant correlate NVDA AMD AVGO --provider gemini --model gemini-2.5-pro
sadquant research NVDA "What setup should I monitor?" --provider openai --model gpt-5.5
sadquant research NVDA "What setup should I monitor?" --provider groq --model openai/gpt-oss-20b
sadquant research NVDA "What setup should I monitor?" --provider gemini --model gemini-2.5-pro
sadquant research NVDA "What setup should I monitor?" --provider anthropic --model claude-sonnet-4-20250514
sadquant research NVDA "What setup should I monitor?" --provider codex --model gpt-5.5
sadquant research NVDA "What setup should I monitor?" --provider cli
```

Default provider can also be set globally:

```powershell
$env:SADQUANT_AI_PROVIDER="codex"
$env:SADQUANT_MODEL="gpt-5.5"
```

Subscription-backed local CLI:

```powershell
$env:SADQUANT_AI_PROVIDER="codex"
codex login
sadquant research NVDA "What setup should I monitor?" --provider codex --finviz
```

Generic subscription-backed local CLI:

```powershell
$env:SADQUANT_AI_PROVIDER="cli"
$env:SADQUANT_CLI_COMMAND="claude -p"
sadquant research NVDA "What setup should I monitor?" --provider cli --finviz
```

These pass SadQuant's tool/RAG packet to an official authenticated CLI over stdin and read stdout. They do not read, copy, or reuse private OAuth/session tokens.

Expanded run:

```powershell
sadquant research NVDA "What changed today?" --web --sentiment --funda
```

Agentic structured research:

```powershell
sadquant research NVDA "What changed and what signal should I monitor?" --agentic --horizon intraday
sadquant research NVDA "What is the 1-8 week setup?" --agentic --horizon swing --finviz --insiders
sadquant research NVDA "What is the 3-18 month thesis risk?" --agentic --horizon position --journal-signal
```

Agentic mode uses a deterministic orchestrator around specialist packets:

- Data Retriever: hybrid RAG and provider context.
- Sentiment Analyst: sentiment/news interpretation when supplied.
- Technical Analyzer: price action, trend, RSI, volatility, and deterministic signals.
- Fundamental Analyst: valuation, fundamentals, estimates, catalysts, transcripts, and filings when supplied.
- Risk Manager: freshness, missing data, volatility, liquidity, correlation, and event risk.
- Verifier/Critic: cited claims, unsupported-claim warnings, confidence, and self-critique.

FMP deep research auto-runs when `FMP_API_KEY` is set:

```powershell
sadquant research NVDA "Build a full long/short dossier"
sadquant research NVDA "Use only non-FMP tools" --no-fmp
sadquant ingest-fmp NVDA --limit 10 --news --press-releases --transcripts
sadquant ingest-fmp NVDA --limit 10 --news --press-releases --transcripts --contextualize
```

Hybrid local RAG search:

```powershell
sadquant ask NVDA "What changed in guidance?" --hybrid --horizon swing
sadquant ask NVDA "What are long-term thesis risks?" --hybrid --horizon position
```

Hybrid retrieval keeps the local SQLite stack but adds contextual chunks, labels, local vector scoring, rank fusion, and stable source ids for citation/evaluation.

Finviz-style snapshot and financial rows:

```powershell
sadquant research ORCL "Summarize valuation, profitability, ownership, and technical setup" --finviz
sadquant research SNDK "Do earnings, margins, and valuation support the stock?" --finviz
```

Insider activity:

```powershell
sadquant insiders NVDA
sadquant research NVDA "What are insiders doing and does it confirm the setup?" --insiders --finviz
```

## RAG Accuracy Evaluation

SadQuant includes a local factual retrieval benchmark:

```powershell
sadquant eval rag --dataset evals/rag.jsonl --report reports/rag-eval.json
```

Dataset rows are JSONL:

```json
{"ticker":"NVDA","horizon":"swing","question":"What changed in guidance?","expected_facts":["data center revenue guidance increased"],"accepted_source_ids":["NVDA:fmp:news:1:1"],"required_claims":["Blackwell demand"],"forbidden_claims":["insiders bought shares"]}
```

The eval reports:

- Fact accuracy
- Citation coverage
- Unsupported-claim rate
- Retrieval recall@k
- MRR
- nDCG
- Abstention quality
- Tool-error rate

## Signal Journal

Agentic research can persist structured signals for later review:

```powershell
sadquant research NVDA "What setup should I monitor?" --agentic --horizon swing --journal-signal
sadquant signals journal --horizon swing
sadquant signals label 1 win --notes "Reached target before invalidation."
sadquant eval signals --horizon swing
```

Signal outcome scoring is intentionally separate from factual RAG accuracy. The first benchmark measures whether the system retrieves and cites facts correctly; the journal creates the dataset needed for later forward-return validation.

## Command Reference

Global option:

| Option | Default | Purpose |
| --- | --- | --- |
| `--log-dir PATH` | `./logs` | Directory for per-invocation CLI log files named from the command input. |

### `sadquant chart TICKER`

Draw a terminal candlestick chart for one ticker using Yahoo Finance OHLCV data.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to chart. |
| `--period TEXT` | `6mo` | Yahoo Finance lookback period. |
| `--interval TEXT` | `1d` | Yahoo Finance interval. |
| `--height INTEGER` | `18` | Price chart height in terminal rows. |
| `--width INTEGER` | terminal width | Chart width in terminal columns. |
| `--no-volume` | off | Hide the volume histogram. |
| `--plain` | off | Disable Rich color markup. |

### `sadquant analyze TICKER`

Analyze one ticker with trend, momentum, risk, local RAG context, optional peer correlations, and optional AI synthesis.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to analyze. |
| `--universe TEXT` | `all` | Context universe: `etf`, `gold`, `semis`, `indexes`, or `all`. |
| `--period TEXT` | `1y` | Yahoo Finance lookback period. |
| `--provider TEXT` | env/default | AI provider: `openai`, `groq`, `gemini`, `anthropic`, `codex`, or `cli`. |
| `--model TEXT` | provider default | Override model name for the selected provider. |
| `--no-ai` | off | Skip AI insight synthesis. |

### `sadquant scan`

Scan a universe and rank deterministic long/short research signals.

| Option | Default | Purpose |
| --- | --- | --- |
| `--universe TEXT` | `all` | Universe: `etf`, `gold`, `semis`, `indexes`, or `all`. |
| `--ticker TEXT` / `-t TEXT` | none | Add a custom ticker. Can be repeated. |
| `--top INTEGER` | `12` | Number of rows to show. |
| `--period TEXT` | `1y` | Yahoo Finance lookback period. |
| `--provider TEXT` | env/default | AI provider: `openai`, `groq`, `gemini`, `anthropic`, `codex`, or `cli`. |
| `--model TEXT` | provider default | Override model name for the selected provider. |
| `--no-ai` | off | Skip AI insight synthesis. |

### Investor workstation commands

These commands add deterministic, automation-friendly workflows around the existing research engine. Most support `--format table|json|csv|markdown` and `--output PATH`.

```powershell
sadquant watchlist add semis NVDA AMD AVGO
sadquant watchlist show semis --format json
sadquant screen --universe watchlist:semis --recipe momentum --top 10
sadquant setup NVDA --horizon swing --journal-signal
sadquant compare NVDA AMD AVGO --format csv
sadquant fundamentals NVDA
sadquant earnings NVDA
sadquant thesis add NVDA "AI data center demand remains durable." --horizon position --review-date 2026-06-30
sadquant thesis list --ticker NVDA
sadquant journal stats --horizon swing
sadquant eval returns --horizon swing
```

Screen recipes currently include `momentum`, `relative-strength`, `vcp`, `earnings-gap`, `quality-growth`, and `value-dividend`. Provider-backed fundamentals and earnings remain read-only and fail soft when public data is unavailable.

### `sadquant correlate TICKERS...`

Show a return correlation matrix for two or more tickers.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKERS...` | required | Two or more tickers. |
| `--period TEXT` | `1y` | Yahoo Finance lookback period. |
| `--provider TEXT` | env/default | AI provider: `openai`, `groq`, `gemini`, `anthropic`, `codex`, or `cli`. |
| `--model TEXT` | provider default | Override model name for the selected provider. |
| `--no-ai` | off | Skip AI insight synthesis. |

### `sadquant insiders TICKER`

Show insider transactions, net purchase/sale activity, and insider roster rows.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to inspect. |
| `--limit INTEGER` | `12` | Recent insider transaction rows to show. |

### `sadquant ingest-note TICKER BODY`

Add a manual note to the local RAG store.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to attach the note to. |
| `BODY` | required | Note text to store in local RAG. |
| `--title TEXT` | `Manual note` | Context title. |
| `--source TEXT` | `manual` | Context source label. |

### `sadquant ask TICKER QUESTION`

Retrieve local RAG context for a ticker/question.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to search. |
| `QUESTION` | required | Retrieval question. |
| `--limit INTEGER` | `5` | Number of context snippets. |
| `--hybrid` | off | Use label/BM25/vector hybrid retrieval instead of legacy FTS retrieval. |
| `--horizon TEXT` | `swing` | Retrieval horizon: `intraday`, `swing`, or `position`. Used with `--hybrid`. |

### `sadquant ingest-fmp TICKER`

Store selected FMP long-form context in the local RAG database.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to ingest from FMP. |
| `--limit INTEGER` | `10` | Maximum news/press release rows to ingest. |
| `--news` | off | Ingest FMP stock news. |
| `--press-releases` | off | Ingest FMP press releases. |
| `--transcripts` | off | Ingest latest FMP earnings transcript context. |
| `--contextualize` | off | Add retrieval context prefixes and chunk metadata. |

If none of `--news`, `--press-releases`, or `--transcripts` is supplied, all three are ingested.

### `sadquant research TICKER QUESTION`

Run a tool-backed AI research agent.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `TICKER` | required | Ticker to research. |
| `QUESTION` | required | Research question for the agent. |
| `--web` | off | Include live web search via Tavily or Brave if configured. |
| `--sentiment` | off | Include Adanos sentiment if configured. |
| `--funda` | off | Include Funda stock news if configured. |
| `--finviz` | off | Include Finviz snapshot and financial rows. |
| `--insiders` | off | Include Yahoo Finance insider transactions and net purchase activity. |
| `--provider TEXT` | env/default | AI provider: `openai`, `groq`, `gemini`, `anthropic`, `codex`, or `cli`. |
| `--model TEXT` | provider default | Override model name for the selected provider. |
| `--no-market` | off | Skip yfinance market snapshot. |
| `--no-yahoo` | off | Skip exhaustive Yahoo Finance/yfinance research packet while keeping `market_snapshot`. |
| `--no-rag` | off | Skip local RAG retrieval. |
| `--no-fmp` | off | Disable automatic FMP deep-research tools for this run. |
| `--agentic` | off | Use structured multi-agent research workflow. |
| `--horizon TEXT` | `swing` | Research horizon: `intraday`, `swing`, or `position`. |
| `--journal-signal` | off | Save the structured signal to the local journal. Requires `--agentic` to produce a structured report. |

When `FMP_API_KEY` is configured, FMP deep-research tools are added automatically unless `--no-fmp` is supplied.

### `sadquant eval rag`

Measure local RAG factual retrieval accuracy with JSONL eval cases.

| Option | Default | Purpose |
| --- | --- | --- |
| `--dataset PATH` | required | JSONL eval dataset. |
| `--report PATH` | none | Optional JSON report output path. |
| `--limit INTEGER` | `8` | Top-k retrieval depth. |

### `sadquant eval signals`

Summarize labeled signal outcomes. Forward-return scoring is planned for a later phase.

| Option | Default | Purpose |
| --- | --- | --- |
| `--journal PATH` | default signal journal | Signal journal SQLite path. |
| `--horizon TEXT` | `swing` | Signal horizon: `intraday`, `swing`, or `position`. |

### `sadquant signals journal`

Show saved agentic research signals.

| Option | Default | Purpose |
| --- | --- | --- |
| `--horizon TEXT` | none | Filter by horizon: `intraday`, `swing`, or `position`. |
| `--limit INTEGER` | `20` | Rows to show. |

### `sadquant signals label SIGNAL_ID OUTCOME`

Attach an outcome label to a journaled signal.

| Argument / Option | Default | Purpose |
| --- | --- | --- |
| `SIGNAL_ID` | required | Journal signal id. |
| `OUTCOME` | required | Outcome label, for example `win`, `loss`, `neutral`, or `expired`. |
| `--notes TEXT` | empty | Outcome notes. |

### `sadquant providers`

Show optional finance provider and AI provider availability.

This command has no command-specific options.

### `sadquant tui`

Open the terminal-native interactive shell with normal terminal scrollback, copy/select behavior, prompt-level state, keyboard autocomplete, Markdown rendering, status events, interrupt handling, and colored CLI/chart output. Existing CLI commands are available as one-shot slash commands, for example `/research NVDA "What changed?" --web`, and bare slash commands such as `/chart` enter persistent command modes where later input is executed as arguments for that command. `/plan` mode lets you inspect the next command before executing it with `/run`.

## Development and Verification

Python package metadata lives in `pyproject.toml`; `setup.py` delegates to setuptools for editable installs.

Useful commands:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
python -m pytest

cd ink_tui
npm install
npm run build
npm test
```

Targeted checks for recent TUI work:

```powershell
python -m pytest tests\test_tui_commands.py tests\test_tui_router.py tests\test_agent.py
cd ink_tui
npm run build
npm test
```

The Ink TUI must be built before `sadquant tui` can launch. If `ink_tui/dist/cli.js` is missing, run `npm install` and `npm run build` from `ink_tui/`.

## Signal Model

Signals are deterministic and inspectable:

- Trend: close versus 20/50/200-day moving averages.
- Momentum: 14-day RSI and 20-day return.
- Risk: realized volatility and distance from 52-week range.
- Context: retrieved local notes/news snippets from the RAG store.

The output is a research signal: `LONG_BIAS`, `SHORT_BIAS`, or `NEUTRAL`.

See `docs/AGENT_TOOLS.md` for the agent/tool map and useful finance plugin skills.
