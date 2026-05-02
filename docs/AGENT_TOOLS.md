# SadQuant Agent Tools

This file maps agent capabilities to the installed finance plugins and optional APIs.

## Core Local Tools

- `market_snapshot`: uses `yfinance` for price history, moving averages, RSI, volatility, and deterministic long/short bias.
- `yahoo_research`: uses public `yfinance` ticker data for price/history metadata, financial statements, earnings/events, analyst estimates, recommendations, holders, insider rows, filings, options chains, sustainability, funds data, and Yahoo Finance news. Bulky tables, news, and option chains are capped with omitted-row counts so default research remains prompt-safe.
- `local_rag`: uses local SQLite FTS5 for manually ingested notes, news snippets, thesis updates, and post-trade observations.
- `web_search`: uses Tavily or Brave Search when `TAVILY_API_KEY` or `BRAVE_SEARCH_API_KEY` is configured.
- `finviz_snapshot`: parses the public Finviz quote snapshot table for valuation, growth, ownership, profitability, performance, volatility, analyst target, and volume metrics.
- `finviz_financials`: parses the public Finviz quote-page financial statement table for revenue, margins, income, EPS, and valuation-ratio context.
- `insider_activity`: fetches Yahoo Finance insider transactions, net purchase/sale activity, and insider roster rows so the agent can summarize what insiders are doing.
- `fmp_market`: Financial Modeling Prep quote, historical EOD, RSI, and price change.
- `fmp_fundamentals`: Financial Modeling Prep profile, peers, statements, key metrics, and TTM metrics.
- `fmp_estimates`: Financial Modeling Prep analyst estimates, ratings snapshot, and price target consensus.
- `fmp_catalysts`: Financial Modeling Prep stock news and press releases.
- `fmp_transcripts`: Financial Modeling Prep latest earnings transcript metadata and selected transcript content.
- `fmp_insiders`: Financial Modeling Prep insider trading statistics.
- `fmp_signal_context`: deterministic combined signal context using existing technical scoring plus FMP quality, valuation, analyst, catalyst, and insider evidence.

## Finance Plugin Skills To Use

- `finance-market-analysis:yfinance-data`: default quotes, historical prices, financial statements, options chains, dividends, recommendations, and Yahoo Finance news.
- `finance-market-analysis:stock-correlation`: co-movement, pair trading research, semiconductor sympathy plays, hedges, rolling correlation, and sector clustering.
- `finance-market-analysis:earnings-preview`: upcoming earnings setup, estimate revisions, and catalyst framing.
- `finance-market-analysis:earnings-recap`: post-earnings reaction, guidance changes, and surprise analysis.
- `finance-market-analysis:options-payoff`: options payoff scenarios for defined-risk long/short expressions.
- `finance-market-analysis:stock-liquidity`: liquidity and tradability checks before ranking signals.
- `finance-data-providers:funda-data`: premium real-time quotes, fundamentals, ETF holdings, options flow/GEX, filings, transcripts, congressional trades, macro, and news.
- `finance-data-providers:finance-sentiment`: normalized Reddit, X, news, and Polymarket sentiment comparisons.
- `finance-social-readers:twitter-reader`: raw X/Twitter feed reads when source-level commentary matters.
- `finance-social-readers:yc-reader`: startup/AI infrastructure context when analyzing private-market spillovers into public AI/semis names.

## Local Agent Skills To Use

These are Codex/local-agent skills installed under `C:\Users\marco\.agents\skills`. Use them as routing instructions for this agent workspace; they are not Python `sadquant research` tools unless a workflow explicitly reads and applies the skill files.

Skill-use contract:

- If the user names one of these skills directly, open that skill's `SKILL.md` and follow it for the turn.
- If the task clearly matches one of these skill domains, prefer the matching skill before doing general analysis.
- For multi-step market research, use the narrowest specialist skill first, then use synthesis/review skills only after evidence is gathered.
- Treat skills as reasoning/workflow instructions. Treat SadQuant tools as data providers. Do not substitute a skill for missing market data.

Installed market and trading skills:

- `backtest-expert`
- `breadth-chart-analyst`
- `breakout-trade-planner`
- `canslim-screener`
- `data-quality-checker`
- `dividend-growth-pullback-screener`
- `downtrend-duration-analyzer`
- `dual-axis-skill-reviewer`
- `earnings-calendar`
- `earnings-trade-analyzer`
- `economic-calendar-fetcher`
- `edge-candidate-agent`
- `edge-concept-synthesizer`
- `edge-hint-extractor`
- `edge-pipeline-orchestrator`
- `edge-signal-aggregator`
- `edge-strategy-designer`
- `edge-strategy-reviewer`
- `exposure-coach`
- `finviz-screener`
- `ftd-detector`
- `institutional-flow-tracker`
- `kanchi-dividend-review-monitor`
- `kanchi-dividend-sop`
- `kanchi-dividend-us-tax-accounting`
- `macro-regime-detector`
- `market-breadth-analyzer`
- `market-environment-analysis`
- `market-news-analyst`
- `market-top-detector`
- `options-strategy-advisor`
- `pair-trade-screener`
- `pead-screener`
- `portfolio-manager`
- `position-sizer`
- `scenario-analyzer`
- `sector-analyst`
- `signal-postmortem`
- `stanley-druckenmiller-investment`
- `strategy-pivot-designer`
- `technical-analyst`
- `theme-detector`
- `trade-hypothesis-ideator`
- `trader-memory-core`
- `uptrend-analyzer`
- `us-market-bubble-detector`
- `us-stock-analysis`
- `value-dividend-screener`
- `vcp-screener`

Suggested routing:

- Market regime: `macro-regime-detector`, `market-environment-analysis`, `market-breadth-analyzer`, `breadth-chart-analyst`, `us-market-bubble-detector`, `economic-calendar-fetcher`.
- Single-stock analysis: `us-stock-analysis`, `technical-analyst`, `finviz-screener`, `institutional-flow-tracker`, `earnings-trade-analyzer`, `market-news-analyst`.
- Setups and screens: `canslim-screener`, `vcp-screener`, `breakout-trade-planner`, `pead-screener`, `dividend-growth-pullback-screener`, `value-dividend-screener`, `pair-trade-screener`.
- Trend diagnostics: `uptrend-analyzer`, `downtrend-duration-analyzer`, `ftd-detector`, `market-top-detector`, `theme-detector`, `sector-analyst`.
- Strategy design and review: `edge-pipeline-orchestrator`, `edge-candidate-agent`, `edge-hint-extractor`, `edge-signal-aggregator`, `edge-concept-synthesizer`, `edge-strategy-designer`, `edge-strategy-reviewer`, `strategy-pivot-designer`, `dual-axis-skill-reviewer`, `signal-postmortem`, `backtest-expert`.
- Portfolio and risk: `portfolio-manager`, `position-sizer`, `scenario-analyzer`, `options-strategy-advisor`, `exposure-coach`, `trader-memory-core`.
- Specialized workflows: `earnings-calendar`, `kanchi-dividend-sop`, `kanchi-dividend-review-monitor`, `kanchi-dividend-us-tax-accounting`, `stanley-druckenmiller-investment`, `trade-hypothesis-ideator`, `data-quality-checker`.

Skill capability map:

| Skill | Primary use | Data/API needs |
| --- | --- | --- |
| `sector-analyst` | Sector rotation, cyclical/defensive risk regime, overbought/oversold sectors, market cycle phase, sector-rotation scenarios. | Local/public CSV; optional chart images. |
| `breadth-chart-analyst` | S&P 500 breadth and US uptrend ratio chart interpretation, bull/bear phase diagnosis, tactical and strategic breadth outlook. | Chart images or breadth data. |
| `technical-analyst` | Pure weekly chart analysis for stocks, indices, crypto, and FX: trend, support/resistance, patterns, momentum, trigger levels. | Charts or price data. |
| `market-news-analyst` | Recent 10-day market-moving news review with impact scoring for policy, earnings, geopolitics, commodities, and macro events. | Web search/fetch. |
| `us-stock-analysis` | Full US equity research memo with fundamentals, technicals, valuation, peers, bull/bear case, and risk assessment. | Market/fundamental data. |
| `market-environment-analysis` | Global macro briefing across equities, FX, commodities, yields, sentiment, and indicator templates. | Market data; optional helper script. |
| `market-breadth-analyzer` | Data-driven breadth health score using TraderMonty CSVs and 6-component 0-100 framework. | Public GitHub CSV. |
| `uptrend-analyzer` | Monty uptrend-ratio dashboard analysis across US stocks and sectors with caution overlays and exposure guidance. | Public GitHub CSV. |
| `macro-regime-detector` | 1-2 year structural macro regime detection using cross-asset ratios and sector rotation. | FMP API. |
| `institutional-flow-tracker` | 13F ownership change analysis, superinvestor weighting, accumulation/distribution, holder concentration. | FMP API. |
| `theme-detector` | FINVIZ industry/sector theme detection with heat, lifecycle maturity, confidence, and representative stocks/ETFs. | FINVIZ public + yfinance; optional FMP/FINVIZ Elite. |
| `economic-calendar-fetcher` | Upcoming central bank, inflation, labor, GDP, and high-impact economic events with implications. | FMP API. |
| `earnings-calendar` | Upcoming US earnings calendar by date/timing, focused on mid-cap+ companies. | FMP API. |
| `scenario-analyzer` | 18-month scenario projection from headlines, including first/second/third-order effects and sector/stock impacts. | Web search. |
| `backtest-expert` | Strategy validation workflow: hypothesis, slippage/costs, robustness, walk-forward, OOS, failure analysis. | Local strategy/data inputs. |
| `stanley-druckenmiller-investment` | Macro theme, liquidity, asymmetric risk/reward, technical confirmation, and position-sizing lens. | Market/macro context. |
| `us-market-bubble-detector` | Quantitative bubble-risk scoring with Minsky/Kindleberger framework, risk budgets, profit-taking and short criteria. | Market sentiment, breadth, VIX, margin, IPO and options metrics. |
| `options-strategy-advisor` | Educational options pricing, Greeks, 17+ strategy simulations, P/L comparison, earnings options planning. | FMP stock data; optional user IV. |
| `portfolio-manager` | Portfolio allocation, risk metrics, position review, model-portfolio comparison, and rebalance plan. | Alpaca MCP or manual holdings. |
| `position-sizer` | Offline long-stock position sizing using fixed fractional, ATR, and Kelly methods with portfolio constraints. | Entry/stop/account inputs; no API. |
| `edge-candidate-agent` | Converts observations into research tickets and Phase I-compatible `strategy.yaml` + metadata artifacts. | Local YAML/pipeline files. |
| `trade-hypothesis-ideator` | Generates falsifiable hypothesis cards from market context, trade logs, journal evidence, and exports candidates. | Local JSON/YAML. |
| `strategy-pivot-designer` | Detects stagnant backtest iterations and proposes structurally different strategy pivots. | Local backtest outputs. |
| `edge-strategy-reviewer` | Deterministic quality gate for strategy drafts with PASS/REVISE/REJECT and export eligibility. | Local strategy YAML. |
| `edge-pipeline-orchestrator` | Runs full edge pipeline: detection, hints, synthesis, design, review, revision loop, export. | Local edge-skill artifacts. |
| `edge-signal-aggregator` | Aggregates upstream edge/theme/sector/institutional signals with weights, recency, dedupe, contradiction logs. | Local JSON/YAML outputs. |
| `trader-memory-core` | Persistent thesis lifecycle from idea to active position to postmortem with review scheduling. | Local thesis artifacts. |
| `exposure-coach` | Converts breadth, macro, top/bottom, theme, sector, and flow inputs into equity exposure ceiling and posture. | Upstream skill outputs; FMP optional. |
| `signal-postmortem` | Classifies matured signals, records outcomes, and feeds weight/backlog improvements. | Manual prices or FMP. |
| `market-top-detector` | O'Neil distribution, leading-stock deterioration, and defensive rotation analysis for market-top risk. | Market/breadth data. |
| `downtrend-duration-analyzer` | Historical peak-to-trough duration analysis and HTML histograms by sector/market cap. | FMP API. |
| `ftd-detector` | Follow-through day detection after corrections using O'Neil methodology and exposure re-entry guidance. | FMP API. |
| `earnings-trade-analyzer` | Scores recent post-earnings reactions using gap, pre-trend, volume, MA200, MA50, and timing-aware gap logic. | FMP API. |
| `pead-screener` | Finds PEAD setups after earnings gaps using weekly red-candle pullback and breakout monitoring. | FMP API or earnings-trade output. |
| `vcp-screener` | Screens for Minervini VCP bases, Stage 2 trends, contractions, pivot points, and readiness state. | FMP API. |
| `canslim-screener` | CANSLIM growth screen with earnings, annual growth, new highs, supply/demand, institutions, market direction. | FMP API + Finviz. |
| `value-dividend-screener` | Value/income/growth/quality dividend screen with sustainability and ranked candidates. | FMP API. |
| `dividend-growth-pullback-screener` | Finds high dividend-growth stocks in technical pullbacks using RSI and fundamental dividend analysis. | FINVIZ Elite + FMP API. |
| `kanchi-dividend-sop` | Kanchi-style 5-step US dividend workflow: screen, quality, valuation, profit filter, pullback buy plan. | Market/fundamental data. |
| `kanchi-dividend-review-monitor` | Forced-review anomaly detection with OK/WARN/REVIEW queues; does not auto-sell. | Local rule engine; no API. |
| `kanchi-dividend-us-tax-accounting` | Qualified/ordinary dividend assumptions, holding-period checks, account-location workflow. | Portfolio/tax assumptions. |
| `pair-trade-screener` | Cointegration, hedge ratio, half-life, z-score entry/exit, and market-neutral pair opportunities. | FMP API. |
| `finviz-screener` | Natural-language to FinViz filters, theme/subtheme cross-screening, recipes, and browser opening. | FINVIZ public; optional Elite. |
| `data-quality-checker` | Pre-publication market-doc QA for price scale, notation, dates, allocation totals, and units. | Local markdown; no API. |

## Suggested Agent Roles

- `MacroAgent`: watches indexes, DXY, rates, gold, oil, VIX, and macro calendars.
- `SectorAgent`: scans semis, ETFs, gold miners, and index constituents for relative strength/weakness.
- `SentimentAgent`: compares web/news/social/Polymarket sentiment against price action.
- `RiskAgent`: checks volatility, liquidity, correlation spikes, and invalidation levels.
- `SynthesisAgent`: consumes only tool outputs and writes the final terminal-ready long/short research brief.

## Environment Keys

```powershell
$env:SADQUANT_AI_PROVIDER="codex"
$env:SADQUANT_MODEL="gpt-5.5"
$env:OPENAI_API_KEY="..."
$env:GROQ_API_KEY="..."
$env:SADQUANT_GROQ_MODEL="openai/gpt-oss-20b"
$env:GEMINI_API_KEY="..."
$env:SADQUANT_GEMINI_MODEL="gemini-2.5-pro"
$env:ANTHROPIC_API_KEY="..."
$env:SADQUANT_ANTHROPIC_MODEL="claude-sonnet-4-20250514"
$env:TAVILY_API_KEY="..."
$env:BRAVE_SEARCH_API_KEY="..."
$env:FMP_API_KEY="..."
$env:FMP_BASE_URL="https://financialmodelingprep.com/stable"
$env:FUNDA_API_KEY="..."
$env:ADANOS_API_KEY="..."
```

## AI Model Providers

- `openai`: uses the OpenAI Responses API with `OPENAI_API_KEY`.
- `groq`: uses Groq's OpenAI-compatible Responses API with `GROQ_API_KEY`.
- `gemini`: uses Gemini `generateContent` with `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- `anthropic`: uses Claude Messages API with `ANTHROPIC_API_KEY`.
- `codex`: uses the official Codex CLI, including ChatGPT subscription auth after `codex login`.
- `cli`: sends the tool/RAG packet to an authenticated local CLI command configured with `SADQUANT_CLI_COMMAND`.

`analyze`, `scan`, and `correlate` also synthesize AI Insights from their deterministic command payloads by default. Pass `--provider` and `--model` on those commands to override the global provider, or `--no-ai` to keep only the raw deterministic output.

Example:

```powershell
sadquant analyze NVDA --universe semis --provider codex --model gpt-5.5
sadquant scan --universe semis --top 10 --provider openai --model gpt-5.5
sadquant correlate NVDA AMD AVGO --provider gemini --model gemini-2.5-pro
sadquant research NVDA "What is the long/short setup?" --provider gemini --model gemini-2.5-pro --finviz --insiders --web
```

FMP deep research auto-runs when `FMP_API_KEY` is configured:

```powershell
sadquant research NVDA "Build a full long/short dossier"
sadquant research NVDA "Skip FMP for this run" --no-fmp
sadquant ingest-fmp NVDA --limit 10 --news --press-releases --transcripts
```

Subscription-backed CLI example:

```powershell
$env:SADQUANT_AI_PROVIDER="codex"
codex login
sadquant research NVDA "What is the long/short setup?" --provider codex --finviz
```

Generic external CLI example:

```powershell
$env:SADQUANT_AI_PROVIDER="cli"
$env:SADQUANT_CLI_COMMAND="claude -p"
sadquant research NVDA "What is the long/short setup?" --provider cli --finviz
```

Use official CLI authentication only. Do not copy OAuth tokens out of Claude Code, Codex, ChatGPT, Copilot, or OpenCode credential stores.

Do not let agents place trades. All tools should remain read-only until execution and broker integrations are deliberately designed with separate risk controls.
