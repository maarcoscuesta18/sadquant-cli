from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from sadquant.ai import BaseModelClient, ModelError, StatusCallback, create_model
from sadquant.tui_commands import CLI_COMMAND_META, SlashCommand


@dataclass(frozen=True)
class RouteDecision:
    command: Optional[SlashCommand]
    reason: str
    clarification: Optional[str] = None
    confirmation_command: Optional[SlashCommand] = None


ROUTER_INSTRUCTIONS = """
You are SadQuant's TUI intent router.

Convert one free-text user request into exactly one existing SadQuant CLI command.
Return strict JSON only, with these keys:
- command: one of analyze, ask, chart, compare, correlate, earnings, fundamentals, insiders, providers, research, scan, screen, setup
- args: JSON array of CLI argument strings
- reason: one short sentence explaining the route
- clarification: null, or a short question when required information is missing

Rules:
- Never return shell commands.
- Never invent options outside the supplied command menu.
- Prefer research TICKER "original question" --agentic for broad market research.
- Prefer analyze for deterministic score, signal, trend, or momentum.
- Prefer ask TICKER "original question" --hybrid only for local notes/RAG/context.
- Prefer chart for chart/candlestick/price-action visualization.
- Prefer correlate for pair or multi-ticker relationship requests.
- Prefer compare for multi-ticker ranking across signal, momentum, and risk metrics when correlation is not specifically requested.
- Prefer scan for ranking or screening universes.
- Prefer screen for named recipe screens such as momentum, VCP, quality-growth, value-dividend, earnings-gap, or relative-strength.
- Prefer setup for deterministic setup plans, entries, invalidation, targets, or watch items.
- Prefer fundamentals for valuation, profitability, growth, or ownership fields.
- Prefer earnings for earnings calendars, estimates, or earnings history.
- Prefer insiders for insider buying/selling/ownership requests.
- Prefer providers for provider, API key, or configuration status requests.
- If no ticker is written but context_tickers is supplied, use the first context ticker for follow-up requests.
- If a ticker or universe is required and missing, set command to null and ask for clarification.
"""


STOPWORDS = {
    "A",
    "ABOUT",
    "AFTER",
    "ALL",
    "AM",
    "AN",
    "AND",
    "API",
    "ARE",
    "AS",
    "AT",
    "BE",
    "BEAR",
    "BEST",
    "BULL",
    "BUY",
    "BY",
    "CAN",
    "CASE",
    "CHART",
    "CLI",
    "DO",
    "DOES",
    "FOR",
    "FROM",
    "GIVE",
    "HAS",
    "HAVE",
    "HOW",
    "I",
    "IN",
    "INTO",
    "IS",
    "IT",
    "KEY",
    "LONG",
    "LONGS",
    "ME",
    "MY",
    "NEWS",
    "NOW",
    "OF",
    "ON",
    "OR",
    "PRICE",
    "RANK",
    "RISK",
    "S",
    "SAY",
    "SCAN",
    "SELL",
    "SETUP",
    "SHORT",
    "SHORTS",
    "SHOULD",
    "SHOW",
    "SIGNAL",
    "STILL",
    "TELL",
    "THE",
    "TO",
    "TODAY",
    "TREND",
    "TUI",
    "VS",
    "WAS",
    "WATCH",
    "WHAT",
    "WHEN",
    "WHERE",
    "WHICH",
    "WHY",
    "WITH",
}

UNIVERSE_ALIASES = {
    "all": "all",
    "etf": "etf",
    "etfs": "etf",
    "gold": "gold",
    "index": "indexes",
    "indexes": "indexes",
    "indices": "indexes",
    "semi": "semis",
    "semis": "semis",
    "semiconductor": "semis",
    "semiconductors": "semis",
}

COMPANY_ALIASES = {
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "amd": "AMD",
    "apple": "AAPL",
    "broadcom": "AVGO",
    "google": "GOOGL",
    "intel": "INTC",
    "meta": "META",
    "microsoft": "MSFT",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "oracle": "ORCL",
    "palantir": "PLTR",
    "tesla": "TSLA",
}

PERIOD_PATTERN = re.compile(r"\b(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)\b", re.IGNORECASE)
INTERVAL_PATTERN = re.compile(r"\b(1m|2m|5m|15m|30m|60m|90m|1h|1d|5d|1wk|1mo|3mo)\b", re.IGNORECASE)
TOP_PATTERN = re.compile(r"\btop\s+(\d{1,3})\b", re.IGNORECASE)
TICKER_PATTERN = re.compile(r"(?<![$A-Za-z])\$?[A-Za-z]{1,5}(?:\.[A-Za-z])?\b")


def route_free_text(
    text: str,
    model: Optional[BaseModelClient] = None,
    context_tickers: Optional[list[str]] = None,
    on_status: Optional[StatusCallback] = None,
) -> RouteDecision:
    cleaned = _clean_text(text)
    if not cleaned:
        return RouteDecision(command=None, reason="", clarification="Ask a question or enter a slash command.")

    decision = _rule_route(cleaned, context_tickers=_normalize_context_tickers(context_tickers))
    if decision is not None:
        return decision

    return _llm_route(cleaned, model=model, context_tickers=_normalize_context_tickers(context_tickers), on_status=on_status)


def validate_routed_command(command: str, args: Any, original_text: str) -> SlashCommand:
    if not isinstance(command, str) or command not in CLI_COMMAND_META:
        raise ValueError("Router returned an unknown SadQuant command.")
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("Router returned invalid command arguments.")

    normalized = _normalize_args(command, args)
    _validate_options(command, normalized)
    _validate_required_args(command, normalized)
    return SlashCommand(name=command, args=normalized, raw=original_text)


def _rule_route(text: str, context_tickers: list[str]) -> Optional[RouteDecision]:
    lower = text.lower()
    tickers = _extract_tickers(text)
    context_ticker = context_tickers[0] if context_tickers else None

    if tickers and _only_tickers(text, tickers):
        return RouteDecision(
            command=None,
            reason="bare ticker",
            clarification=f"What should I do with {', '.join(tickers)}? Try asking for research, a chart, a signal, or correlation.",
        )

    if _contains_any(lower, ["provider", "providers", "api key", "configured", "configuration"]):
        return _decision("providers", [], "provider/configuration status")

    if _is_correlate_request(lower, tickers):
        if len(tickers) < 2:
            return RouteDecision(command=None, reason="correlation request", clarification="Which two or more tickers should I correlate?")
        return _decision("correlate", tickers, "pair or multi-ticker correlation request")

    if len(tickers) >= 2 and _contains_any(lower, ["compare", "rank these", "which is better"]):
        return _decision("compare", tickers, "multi-ticker comparison request")

    if _contains_any(lower, ["screen", "screener", "vcp", "canslim", "quality-growth", "quality growth", "value-dividend", "value dividend", "earnings-gap", "earnings gap", "relative strength"]):
        args = ["--universe", _extract_universe(lower)]
        recipe = _extract_recipe(lower)
        if recipe:
            args.extend(["--recipe", recipe])
        top = _extract_top(lower)
        if top is not None:
            args.extend(["--top", str(top)])
        return _decision("screen", args, "named investor screen request")

    if _contains_any(lower, ["scan", "rank", "best longs", "best shorts"]):
        args = ["--universe", _extract_universe(lower)]
        top = _extract_top(lower)
        if top is not None:
            args.extend(["--top", str(top)])
        return _decision("scan", args, "screening/ranking request")

    if _contains_any(lower, ["chart", "candles", "candlestick", "price action"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="chart request", clarification="Which ticker should I chart?")
        args = [tickers[0]]
        period = _extract_period(text)
        interval = _extract_interval(text)
        if period:
            args.extend(["--period", period])
        if interval and interval != period:
            args.extend(["--interval", interval])
        return _decision("chart", args, "chart/price-action request")

    if _contains_any(lower, ["insider", "insiders", "insider buying", "insider selling"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="insider activity request", clarification="Which ticker should I check for insider activity?")
        return _decision("insiders", [tickers[0]], "insider activity request")

    if _contains_any(lower, ["setup", "entry", "invalidation", "target", "watch items", "watch item"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="setup request", clarification="Which ticker should I build a setup for?")
        args = [tickers[0]]
        horizon = _extract_horizon(lower)
        if horizon is not None:
            args.extend(["--horizon", horizon])
        return _decision("setup", args, "deterministic setup request")

    if _contains_any(lower, ["fundamental", "fundamentals", "valuation", "profitability", "ownership"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="fundamentals request", clarification="Which ticker should I inspect for fundamentals?")
        return _decision("fundamentals", [tickers[0]], "fundamentals request")

    if _contains_any(lower, ["earnings calendar", "earnings date", "earnings estimate", "earnings history"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="earnings request", clarification="Which ticker should I inspect for earnings?")
        return _decision("earnings", [tickers[0]], "earnings data request")

    if _contains_any(lower, ["notes", "local context", "rag", "stored context", "my context"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="local context request", clarification="Which ticker should I search local context for?")
        return _decision("ask", [tickers[0], text, "--hybrid"], "local RAG/context request")

    if _contains_any(lower, ["score", "signal", "trend", "momentum"]):
        if not tickers and context_ticker:
            tickers = [context_ticker]
        if not tickers:
            return RouteDecision(command=None, reason="deterministic signal request", clarification="Which ticker should I analyze?")
        return _decision("analyze", [tickers[0]], "deterministic signal request")

    if not tickers and context_ticker and _contains_any(
        lower,
        [
            "what changed",
            "changed",
            "risk",
            "risks",
            "catalyst",
            "catalysts",
            "bull case",
            "bear case",
            "setup",
            "watch",
            "earnings",
            "guidance",
            "valuation",
            "fundamental",
            "fundamentals",
            "margins",
            "profitability",
            "news",
            "latest",
            "today",
            "expect",
            "expected",
            "expectations",
        ],
    ):
        tickers = [context_ticker]

    if tickers and _contains_any(
        lower,
        [
            "what changed",
            "changed",
            "risk",
            "risks",
            "catalyst",
            "catalysts",
            "bull case",
            "bear case",
            "setup",
            "watch",
            "earnings",
            "guidance",
            "valuation",
            "fundamental",
            "fundamentals",
            "margins",
            "profitability",
            "news",
            "latest",
            "today",
            "expect",
            "expected",
            "expectations",
        ],
    ):
        reason = "follow-up research request" if context_ticker and tickers[0] == context_ticker and context_ticker not in _extract_tickers(text) else "broad research request"
        return _decision("research", _research_args(tickers[0], text, lower), reason)

    if tickers and _looks_like_question(lower):
        return _decision("research", _research_args(tickers[0], text, lower), "general ticker question")

    return None


def _llm_route(
    text: str,
    model: Optional[BaseModelClient],
    context_tickers: list[str],
    on_status: Optional[StatusCallback] = None,
) -> RouteDecision:
    selected = model or create_model()
    if not selected.available():
        return RouteDecision(
            command=None,
            reason="router unavailable",
            clarification="I could not confidently route that. Add a ticker and what you want, or use a slash command like /research.",
        )

    prompt = json.dumps(
        {
            "request": text,
            "detected_tickers": _extract_tickers(text),
            "context_tickers": context_tickers,
            "commands": {
                name: {
                    "description": meta.description,
                    "options": meta.options,
                    "examples": meta.examples,
                }
                for name, meta in CLI_COMMAND_META.items()
                if name in {"analyze", "ask", "chart", "compare", "correlate", "earnings", "fundamentals", "insiders", "providers", "research", "scan", "screen", "setup"}
            },
        },
        indent=2,
        sort_keys=True,
    )
    try:
        if on_status is not None:
            on_status(f"Routing with {selected.provider}:{selected.model}")
        response = selected.complete(prompt, ROUTER_INSTRUCTIONS, on_status=on_status)
        payload = _parse_router_json(response.text)
        clarification = payload.get("clarification")
        command = payload.get("command")
        reason = str(payload.get("reason") or "LLM-routed request")
        confirmation_command = None
        if command:
            try:
                confirmation_command = validate_routed_command(str(command), payload.get("args", []), text)
            except ValueError:
                confirmation_command = None
        if clarification:
            return RouteDecision(
                command=None,
                reason=reason,
                clarification=str(clarification),
                confirmation_command=confirmation_command,
            )
        slash_command = confirmation_command or validate_routed_command(str(command), payload.get("args", []), text)
        return RouteDecision(command=slash_command, reason=reason)
    except (ModelError, ValueError, json.JSONDecodeError) as exc:
        return RouteDecision(
            command=None,
            reason="router failed",
            clarification=f"I could not route that request safely: {exc}",
        )


def _decision(command: str, args: list[str], reason: str) -> RouteDecision:
    slash_command = validate_routed_command(command, args, " ".join([command, *args]).strip())
    return RouteDecision(command=slash_command, reason=reason)


def _research_args(ticker: str, text: str, lower: str) -> list[str]:
    args = [ticker, text, "--agentic"]
    if _contains_any(lower, ["today", "latest", "news", "what changed", "changed"]):
        args.append("--web")
    if _contains_any(
        lower,
        ["valuation", "margin", "margins", "profitability", "fundamental", "fundamentals", "financial", "financials", "technical", "earnings", "guidance"],
    ):
        args.append("--finviz")
    if _contains_any(lower, ["insider", "insiders", "insider buying", "insider selling"]):
        args.append("--insiders")
    horizon = _extract_horizon(lower)
    if horizon is not None:
        args.extend(["--horizon", horizon])
    return args


def _validate_options(command: str, args: list[str]) -> None:
    allowed = set(CLI_COMMAND_META[command].options)
    index = 0
    while index < len(args):
        arg = args[index]
        if not arg.startswith("-"):
            index += 1
            continue
        if arg not in allowed:
            raise ValueError(f"Router returned unsupported option '{arg}' for {command}.")
        index += 1


def _validate_required_args(command: str, args: list[str]) -> None:
    positional = [arg for arg in args if not arg.startswith("-")]
    if command in {"analyze", "chart", "earnings", "fundamentals", "insiders", "setup"} and len(positional) < 1:
        raise ValueError(f"{command} requires a ticker.")
    if command in {"ask", "research"} and len(positional) < 2:
        raise ValueError(f"{command} requires a ticker and question.")
    if command in {"compare", "correlate"} and len(positional) < 2:
        raise ValueError(f"{command} requires at least two tickers.")


def _normalize_args(command: str, args: list[str]) -> list[str]:
    allowed = CLI_COMMAND_META[command].options
    normalized: list[str] = []
    for arg in args:
        if not arg.startswith("-") or arg in allowed:
            normalized.append(arg)
            continue
        matches = [option for option in allowed if option.startswith(arg)]
        normalized.append(matches[0] if len(matches) == 1 else arg)
    return normalized


def _parse_router_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _extract_tickers(text: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    lower = text.lower()
    for alias, ticker in COMPANY_ALIASES.items():
        match = re.search(rf"\b{re.escape(alias)}\b", lower)
        if match:
            candidates.append((match.start(), ticker))
    for match in TICKER_PATTERN.finditer(text):
        raw = match.group(0)
        explicit_symbol = raw.startswith("$")
        token = raw[1:] if explicit_symbol else raw
        value = token.upper()
        if value in STOPWORDS or value.lower() in UNIVERSE_ALIASES or value.lower() in COMPANY_ALIASES:
            continue
        plain_length = len(value.replace(".", ""))
        if plain_length == 1 and not explicit_symbol and token != token.upper():
            continue
        if token != token.upper() and plain_length > 4:
            continue
        candidates.append((match.start(), value))

    tickers: list[str] = []
    for _position, ticker in sorted(candidates, key=lambda item: item[0]):
        if ticker in tickers:
            continue
        tickers.append(ticker)
    return tickers


def _extract_universe(lower: str) -> str:
    for alias, universe in UNIVERSE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return universe
    return "all"


def _extract_top(lower: str) -> Optional[int]:
    match = TOP_PATTERN.search(lower)
    if not match:
        return None
    return max(1, min(100, int(match.group(1))))


def _extract_recipe(lower: str) -> Optional[str]:
    if "relative strength" in lower or "relative-strength" in lower:
        return "relative-strength"
    if "earnings gap" in lower or "earnings-gap" in lower:
        return "earnings-gap"
    if "quality growth" in lower or "quality-growth" in lower:
        return "quality-growth"
    if "value dividend" in lower or "value-dividend" in lower:
        return "value-dividend"
    if "vcp" in lower:
        return "vcp"
    if "momentum" in lower:
        return "momentum"
    return None


def _extract_period(text: str) -> Optional[str]:
    match = PERIOD_PATTERN.search(text)
    return match.group(1).lower() if match else None


def _extract_interval(text: str) -> Optional[str]:
    match = INTERVAL_PATTERN.search(text)
    return match.group(1).lower() if match else None


def _extract_horizon(lower: str) -> Optional[str]:
    if _contains_any(lower, ["intraday", "today", "day trade", "this session"]):
        return "intraday"
    if _contains_any(lower, ["swing", "this week", "next week", "1-8 week", "1 to 8 week"]):
        return "swing"
    if _contains_any(lower, ["position", "long term", "long-term", "months", "years"]):
        return "position"
    return None


def _is_correlate_request(lower: str, tickers: list[str]) -> bool:
    return len(tickers) >= 2 and _contains_any(lower, ["correlation", "correlate", " vs ", " versus "])


def _looks_like_question(lower: str) -> bool:
    return "?" in lower or _contains_any(lower, ["what", "why", "how", "should", "is ", "are ", "can "])


def _only_tickers(text: str, tickers: list[str]) -> bool:
    tokens = [token.upper() for token in re.findall(r"[A-Za-z]{1,5}(?:\.[A-Za-z])?", text)]
    return bool(tokens) and tokens == tickers


def _contains_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def _normalize_context_tickers(context_tickers: Optional[list[str]]) -> list[str]:
    if not context_tickers:
        return []
    normalized: list[str] = []
    for ticker in context_tickers:
        value = ticker.upper().strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized
