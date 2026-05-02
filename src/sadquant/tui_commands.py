from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import shlex


@dataclass(frozen=True)
class CommandTemplate:
    value: str
    label: str
    description: str
    replace_token: bool = True


@dataclass(frozen=True)
class ParameterSuggestion:
    after_args: int
    value: str
    label: str
    description: str
    replace_token: bool = True


@dataclass(frozen=True)
class OptionSpec:
    flag: str
    aliases: tuple[str, ...]
    value_type: Literal["bool", "choice", "int", "text", "path"] = "text"
    choices: tuple[str, ...] = ()
    default: Optional[str] = None
    repeatable: bool = False
    description: str = ""


@dataclass(frozen=True)
class CommandMeta:
    name: str
    description: str
    examples: tuple[str, ...] = ()
    options: tuple[str, ...] = ()
    option_specs: tuple[OptionSpec, ...] = ()
    subcommands: tuple[str, ...] = ()
    templates: tuple[CommandTemplate, ...] = ()
    parameter_suggestions: tuple[ParameterSuggestion, ...] = ()


CLI_COMMAND_META = {
    "analyze": CommandMeta(
        name="analyze",
        description="Analyze one ticker with deterministic signals and optional AI.",
        examples=('NVDA --universe semis',),
        options=("--universe", "--period", "--provider", "--model", "--no-ai"),
        templates=(
            CommandTemplate(
                value="NVDA --universe semis --no-ai",
                label="example analyze",
                description="Ticker plus universe; add --no-ai when you only want deterministic signals.",
            ),
        ),
    ),
    "ask": CommandMeta(
        name="ask",
        description="Retrieve local RAG context for a ticker and question.",
        examples=('NVDA "What are the main risks?" --hybrid',),
        options=("--limit", "--hybrid", "--horizon"),
        templates=(
            CommandTemplate(
                value='NVDA "What are the main risks to the next quarter?" --hybrid',
                label="example ask",
                description="Ticker plus a quoted question; use --hybrid for label/BM25/vector retrieval.",
            ),
        ),
        parameter_suggestions=(
            ParameterSuggestion(
                after_args=1,
                value='"What are the main risks to the next quarter?"',
                label="question prompt",
                description="Ask a specific, quoted question about risks, catalysts, valuation, or setup.",
            ),
        ),
    ),
    "chart": CommandMeta(
        name="chart",
        description="Draw a terminal candlestick chart for one ticker.",
        examples=("NVDA --period 6mo --interval 1d",),
        options=("--period", "--interval", "--height", "--width", "--no-volume", "--plain"),
        templates=(
            CommandTemplate(
                value="NVDA --period 6mo --interval 1d",
                label="example chart",
                description="Ticker plus lookback period and candle interval.",
            ),
        ),
    ),
    "correlate": CommandMeta(
        name="correlate",
        description="Show a return correlation matrix for tickers.",
        examples=("NVDA AMD --period 1y",),
        options=("--period", "--provider", "--model", "--no-ai"),
        templates=(
            CommandTemplate(
                value="NVDA AMD --period 1y --no-ai",
                label="example correlate",
                description="Two or more tickers plus a lookback period.",
            ),
        ),
    ),
    "compare": CommandMeta(
        name="compare",
        description="Compare deterministic signal, momentum, and risk metrics across tickers.",
        examples=("NVDA AMD AVGO --period 1y",),
        options=("--period", "--format", "--output"),
        templates=(
            CommandTemplate(
                value="NVDA AMD AVGO --period 1y",
                label="example compare",
                description="Two or more tickers plus a lookback period.",
            ),
        ),
    ),
    "eval": CommandMeta(
        name="eval",
        description="Evaluate retrieval and signal quality.",
        examples=("rag --dataset evals/rag.jsonl", "signals --horizon swing"),
        options=("--dataset", "--report", "--limit", "--journal", "--horizon"),
        subcommands=("rag", "signals", "returns"),
        templates=(
            CommandTemplate(
                value="rag --dataset evals/rag.jsonl",
                label="example eval rag",
                description="Evaluate retrieval cases from a JSONL dataset.",
            ),
            CommandTemplate(
                value="signals --horizon swing",
                label="example eval signals",
                description="Summarize labeled signal journal outcomes for one horizon.",
            ),
            CommandTemplate(
                value="returns --horizon swing",
                label="example eval returns",
                description="Compute forward returns for journaled signals.",
            ),
        ),
    ),
    "earnings": CommandMeta(
        name="earnings",
        description="Show Yahoo Finance earnings calendar, estimates, and history payloads.",
        examples=("NVDA",),
        options=("--format", "--output"),
        templates=(CommandTemplate(value="NVDA", label="example earnings", description="Ticker to inspect."),),
    ),
    "fundamentals": CommandMeta(
        name="fundamentals",
        description="Show deterministic valuation, profitability, growth, and ownership fields.",
        examples=("NVDA",),
        options=("--format", "--output"),
        templates=(CommandTemplate(value="NVDA", label="example fundamentals", description="Ticker to inspect."),),
    ),
    "ingest-fmp": CommandMeta(
        name="ingest-fmp",
        description="Store selected FMP long-form context in local RAG.",
        examples=("NVDA --news --transcripts",),
        options=("--limit", "--news", "--press-releases", "--transcripts", "--contextualize"),
        templates=(
            CommandTemplate(
                value="NVDA --news --transcripts --contextualize",
                label="example ingest-fmp",
                description="Ticker plus the FMP context types to store locally.",
            ),
        ),
    ),
    "ingest-note": CommandMeta(
        name="ingest-note",
        description="Add a manual note to local RAG.",
        examples=('NVDA "New export controls may affect guidance."',),
        options=("--title", "--source"),
        templates=(
            CommandTemplate(
                value='NVDA "New export controls may affect guidance." --title "Export control note"',
                label="example note",
                description="Ticker plus a quoted note body; add title/source for cleaner retrieval.",
            ),
        ),
        parameter_suggestions=(
            ParameterSuggestion(
                after_args=1,
                value='"Summarize the concrete evidence, date, and why it matters for this ticker."',
                label="note prompt",
                description="Write a quoted note with evidence, timing, and investment relevance.",
            ),
        ),
    ),
    "insiders": CommandMeta(
        name="insiders",
        description="Show insider buying, selling, and holding activity.",
        examples=("NVDA --limit 12",),
        options=("--limit",),
        templates=(
            CommandTemplate(
                value="NVDA --limit 12",
                label="example insiders",
                description="Ticker plus the number of recent insider rows to show.",
            ),
        ),
    ),
    "providers": CommandMeta(
        name="providers",
        description="Show provider availability.",
        examples=("",),
    ),
    "journal": CommandMeta(
        name="journal",
        description="Inspect investor journal statistics.",
        examples=("stats --horizon swing",),
        options=("--horizon", "--limit", "--format", "--output"),
        subcommands=("stats",),
        templates=(CommandTemplate(value="stats --horizon swing", label="example journal stats", description="Summarize signal journal outcome labels."),),
    ),
    "research": CommandMeta(
        name="research",
        description="Run a tool-backed AI research agent.",
        examples=('NVDA "What changed?" --web --finviz',),
        options=(
            "--web",
            "--sentiment",
            "--funda",
            "--finviz",
            "--insiders",
            "--provider",
            "--model",
            "--no-market",
            "--no-yahoo",
            "--no-rag",
            "--no-fmp",
            "--agentic",
            "--horizon",
            "--journal-signal",
        ),
        templates=(
            CommandTemplate(
                value='NVDA "What changed in earnings, guidance, estimates, and price action?" --web --finviz',
                label="example research",
                description="Ticker plus a quoted research question and the tools you want included.",
            ),
        ),
        parameter_suggestions=(
            ParameterSuggestion(
                after_args=1,
                value='"What changed in earnings, guidance, estimates, and price action?"',
                label="research prompt",
                description="Ask for concrete changes, evidence, catalysts, risks, and the time horizon.",
            ),
            ParameterSuggestion(
                after_args=1,
                value='"Build a bull, bear, and base case using only cited evidence."',
                label="scenario prompt",
                description="Use a quoted prompt when you want the agent to structure its answer.",
            ),
        ),
    ),
    "scan": CommandMeta(
        name="scan",
        description="Scan a universe or watchlist and rank long/short signals.",
        examples=("--universe all --top 10",),
        options=("--universe", "--ticker", "-t", "--top", "--period", "--provider", "--model", "--no-ai"),
        templates=(
            CommandTemplate(
                value="--universe all --top 10 --no-ai",
                label="example scan",
                description="Universe plus row count; add --ticker to include custom symbols.",
            ),
        ),
    ),
    "screen": CommandMeta(
        name="screen",
        description="Run a named deterministic investor screen.",
        examples=("--universe semis --recipe momentum --top 10",),
        options=("--universe", "--ticker", "-t", "--recipe", "--top", "--period", "--format", "--output"),
        templates=(
            CommandTemplate(
                value="--universe semis --recipe momentum --top 10",
                label="example screen",
                description="Universe plus named recipe and row count.",
            ),
        ),
    ),
    "setup": CommandMeta(
        name="setup",
        description="Build a deterministic swing or position setup brief.",
        examples=("NVDA --horizon swing",),
        options=("--horizon", "--period", "--journal-signal", "--format", "--output"),
        templates=(CommandTemplate(value="NVDA --horizon swing", label="example setup", description="Ticker plus setup horizon."),),
    ),
    "signals": CommandMeta(
        name="signals",
        description="Save and inspect generated research signals.",
        examples=("journal --horizon swing", "label 1 win --notes reached-target"),
        options=("--horizon", "--limit", "--notes"),
        subcommands=("journal", "label"),
        templates=(
            CommandTemplate(
                value="journal --horizon swing --limit 20",
                label="example journal",
                description="Inspect saved signals for a horizon.",
            ),
            CommandTemplate(
                value='label 1 win --notes "Reached target after earnings."',
                label="example label",
                description="Attach an outcome and concise quoted notes to a signal id.",
            ),
        ),
    ),
    "thesis": CommandMeta(
        name="thesis",
        description="Track long-term thesis records and review cadence.",
        examples=('add NVDA "AI data center thesis" --horizon position', "list --ticker NVDA"),
        options=("--ticker", "-t", "--horizon", "--evidence", "--risks", "--review-date", "--status", "--limit", "--format", "--output"),
        subcommands=("add", "list"),
        templates=(
            CommandTemplate(value='add NVDA "AI data center thesis" --horizon position', label="example thesis add", description="Create a thesis record."),
            CommandTemplate(value="list --ticker NVDA", label="example thesis list", description="List thesis records for a ticker."),
        ),
    ),
    "watchlist": CommandMeta(
        name="watchlist",
        description="Create and inspect persistent ticker watchlists.",
        examples=("add semis NVDA AMD AVGO", "show semis"),
        options=("--format", "--output"),
        subcommands=("add", "remove", "show", "list"),
        templates=(
            CommandTemplate(value="add semis NVDA AMD AVGO", label="example watchlist add", description="Add tickers to a watchlist."),
            CommandTemplate(value="show semis", label="example watchlist show", description="Show one watchlist."),
        ),
    ),
}

CLI_COMMANDS = set(CLI_COMMAND_META)
MODE_COMMANDS = CLI_COMMANDS - {"providers"}

OPTION_SPEC_BY_FLAG: dict[str, OptionSpec] = {
    "--agentic": OptionSpec("--agentic", ("agentic",), "bool", description="Use structured agentic research."),
    "--contextualize": OptionSpec("--contextualize", ("contextualize", "context"), "bool", description="Add contextual RAG chunk metadata."),
    "--dataset": OptionSpec("--dataset", ("dataset", "data"), "path", description="Dataset path."),
    "--evidence": OptionSpec("--evidence", ("evidence",), "text", description="Evidence text."),
    "--finviz": OptionSpec("--finviz", ("finviz", "financials"), "bool", description="Include Finviz data."),
    "--format": OptionSpec("--format", ("format",), "choice", ("table", "json", "csv", "markdown"), "table", description="Output format."),
    "--funda": OptionSpec("--funda", ("funda",), "bool", description="Include Funda news."),
    "--height": OptionSpec("--height", ("height",), "int", description="Chart height."),
    "--hybrid": OptionSpec("--hybrid", ("hybrid",), "bool", description="Use hybrid RAG retrieval."),
    "--horizon": OptionSpec("--horizon", ("horizon",), "choice", ("intraday", "swing", "position"), "swing", description="Research horizon."),
    "--insiders": OptionSpec("--insiders", ("insiders", "insider"), "bool", description="Include insider activity."),
    "--interval": OptionSpec("--interval", ("interval",), "choice", ("1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"), "1d", description="Chart interval."),
    "--journal": OptionSpec("--journal", ("journal-path",), "path", description="Signal journal path."),
    "--journal-signal": OptionSpec("--journal-signal", ("journal", "save", "save-signal"), "bool", description="Save signal to journal."),
    "--limit": OptionSpec("--limit", ("limit",), "int", description="Maximum rows."),
    "--model": OptionSpec("--model", ("model",), "text", description="AI model override."),
    "--news": OptionSpec("--news", ("news",), "bool", description="Include news."),
    "--no-ai": OptionSpec("--no-ai", ("ai",), "bool", description="Disable AI insights."),
    "--no-fmp": OptionSpec("--no-fmp", ("fmp",), "bool", description="Disable FMP tools."),
    "--no-market": OptionSpec("--no-market", ("market",), "bool", description="Disable market snapshot."),
    "--no-rag": OptionSpec("--no-rag", ("rag",), "bool", description="Disable local RAG."),
    "--no-volume": OptionSpec("--no-volume", ("volume",), "bool", description="Hide volume."),
    "--no-yahoo": OptionSpec("--no-yahoo", ("yahoo",), "bool", description="Disable Yahoo packet."),
    "--notes": OptionSpec("--notes", ("notes",), "text", description="Outcome notes."),
    "--output": OptionSpec("--output", ("output", "out"), "path", description="Output file path."),
    "--period": OptionSpec("--period", ("period", "lookback"), "choice", ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"), "1y", description="Lookback period."),
    "--plain": OptionSpec("--plain", ("plain",), "bool", description="Disable color markup."),
    "--press-releases": OptionSpec("--press-releases", ("press", "press-releases", "pr"), "bool", description="Include press releases."),
    "--provider": OptionSpec("--provider", ("provider",), "choice", ("openai", "groq", "gemini", "anthropic", "codex", "cli"), description="AI provider."),
    "--recipe": OptionSpec("--recipe", ("recipe",), "choice", ("momentum", "relative-strength", "vcp", "earnings-gap", "quality-growth", "value-dividend"), "momentum", description="Screen recipe."),
    "--report": OptionSpec("--report", ("report",), "path", description="Report output path."),
    "--review-date": OptionSpec("--review-date", ("review", "review-date"), "text", description="Next thesis review date."),
    "--risks": OptionSpec("--risks", ("risks",), "text", description="Risk text."),
    "--sentiment": OptionSpec("--sentiment", ("sentiment",), "bool", description="Include sentiment data."),
    "--status": OptionSpec("--status", ("status",), "text", description="Status filter."),
    "--ticker": OptionSpec("--ticker", ("ticker", "tickers"), "text", repeatable=True, description="Add ticker."),
    "-t": OptionSpec("-t", ("t",), "text", repeatable=True, description="Add ticker."),
    "--title": OptionSpec("--title", ("title",), "text", description="Context title."),
    "--top": OptionSpec("--top", ("top",), "int", default="12", description="Rows to show."),
    "--transcripts": OptionSpec("--transcripts", ("transcripts", "transcript"), "bool", description="Include transcripts."),
    "--universe": OptionSpec("--universe", ("universe",), "choice", ("all", "etf", "gold", "semis", "indexes"), "all", description="Ticker universe."),
    "--web": OptionSpec("--web", ("web",), "bool", description="Include web search."),
    "--width": OptionSpec("--width", ("width",), "int", description="Chart width."),
}

NATIVE_COMMANDS = {"clear", "exit", "exit-mode", "help", "mode", "plan", "quit", "run"}
NATIVE_COMMAND_META = {
    "help": CommandMeta(name="help", description="Show TUI help."),
    "clear": CommandMeta(name="clear", description="Clear the transcript."),
    "plan": CommandMeta(name="plan", description="Toggle plan mode.", examples=("on", "off")),
    "run": CommandMeta(name="run", description="Execute the latest planned command."),
    "mode": CommandMeta(name="mode", description="Enter or leave a command mode.", examples=("chart", "off")),
    "exit-mode": CommandMeta(name="exit-mode", description="Leave the active command mode."),
    "exit": CommandMeta(name="exit", description="Leave the TUI."),
    "quit": CommandMeta(name="quit", description="Leave the TUI."),
}

HELP_TEXT = """SadQuant TUI commands

Free chat:
  what changed for NVDA today?
  chart NVDA 6mo
  compare NVDA vs AMD

One-shot slash commands mirror the CLI:
  /analyze NVDA --universe semis
  /research NVDA "What changed?" --web --finviz
  /chart NVDA --period 6mo
  /scan --universe all --top 10
  /screen --universe semis --recipe momentum --top 10
  /setup NVDA --horizon swing
  /compare NVDA AMD AVGO
  /fundamentals NVDA
  /earnings NVDA
  /correlate NVDA AMD
  /insiders NVDA
  /watchlist add semis NVDA AMD AVGO
  /thesis add NVDA "AI data center thesis" --horizon position
  /journal stats --horizon swing
  /ask NVDA "What are the main risks?"
  /ingest-note NVDA "New export controls may affect guidance."
  /ingest-fmp NVDA --news --transcripts
  /eval rag --dataset evals/rag.jsonl
  /signals journal --horizon swing
  /providers

Modes:
  /chart      Enter chart> mode
  NVDA --period 6mo
  NVDA period 6mo interval 1d
  Ctrl+O      Open an option editor for the active command
  /mode off   Leave the active mode

TUI commands:
  /help       Show this help
  /clear      Clear the transcript
  /plan       Toggle plan mode
  /plan off   Return to normal mode
  /run        Execute the latest planned command
  /exit-mode  Leave the active command mode
  /exit       Leave the TUI
"""


class SlashCommandError(ValueError):
    """Raised when user input cannot be converted to a SadQuant command."""


@dataclass(frozen=True)
class SlashCommand:
    name: str
    args: list[str]
    raw: str
    native: bool = False

    @property
    def argv(self) -> list[str]:
        return [self.name, *self.args]

    @property
    def display(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class CommandAction:
    kind: Literal["clear", "error", "execute", "exit", "help", "mode", "plan", "planned"]
    message: str
    command: Optional[SlashCommand] = None


@dataclass(frozen=True)
class CommandSuggestion:
    value: str
    label: str
    description: str
    replace_token: bool = True


def parse_slash_command(text: str) -> SlashCommand:
    raw = text.strip()
    if not raw:
        raise SlashCommandError("Enter a slash command, for example /help.")
    if not raw.startswith("/"):
        raise SlashCommandError("Commands must start with '/'. Try /help.")

    body = raw[1:].strip()
    if not body:
        raise SlashCommandError("Enter a command after '/'. Try /help.")

    try:
        tokens = [_clean_token(token) for token in shlex.split(body, posix=False)]
    except ValueError as exc:
        raise SlashCommandError(f"Could not parse command: {exc}") from exc

    if not tokens:
        raise SlashCommandError("Enter a command after '/'. Try /help.")

    name = tokens[0].lower()
    args = tokens[1:]
    if name in NATIVE_COMMANDS:
        return SlashCommand(name=name, args=args, raw=raw, native=True)
    if name not in CLI_COMMANDS:
        raise SlashCommandError(f"Unknown command '/{name}'. Try /help.")
    return SlashCommand(name=name, args=_normalize_command_args(name, args), raw=raw)


def command_schema(command_name: str) -> dict[str, object]:
    if command_name not in CLI_COMMAND_META:
        raise SlashCommandError(f"Unknown command '{command_name}'.")
    meta = CLI_COMMAND_META[command_name]
    return {
        "name": meta.name,
        "description": meta.description,
        "examples": list(meta.examples),
        "subcommands": list(meta.subcommands),
        "templates": [template.__dict__ for template in meta.templates],
        "options": [option.__dict__ for option in _option_specs(meta)],
    }


def compose_slash_command(command_name: str, args: list[str]) -> SlashCommand:
    if command_name not in CLI_COMMAND_META:
        raise SlashCommandError(f"Unknown command '{command_name}'.")
    return SlashCommand(name=command_name, args=_normalize_command_args(command_name, args), raw=" ".join([command_name, *args]))


def _clean_token(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
        return token[1:-1]
    return token


class TuiCommandController:
    def __init__(self) -> None:
        self.plan_mode = False
        self.active_command: Optional[str] = None
        self.planned_command: Optional[SlashCommand] = None
        self.pending_confirmation: Optional[SlashCommand] = None
        self.pending_confirmation_reason: Optional[str] = None
        self.context_tickers: list[str] = []

    @property
    def mode_label(self) -> str:
        return "PLAN" if self.plan_mode else "NORMAL"

    @property
    def active_prompt(self) -> str:
        return f"{self.active_command}>" if self.active_command else "/"

    def submit(self, text: str) -> CommandAction:
        stripped = text.strip()
        if not stripped:
            return CommandAction(kind="error", message="Enter a command or arguments.")

        if not stripped.startswith("/"):
            if self.active_command is None:
                if self.pending_confirmation is not None:
                    if _is_affirmative(stripped):
                        command = self.pending_confirmation
                        reason = self.pending_confirmation_reason or "confirmed route"
                        self._clear_pending_confirmation()
                        route_prefix = "Planned route" if self.plan_mode else "Routed to"
                        return self._execute_or_plan(
                            command,
                            message=f"{route_prefix}: sadquant {command.display} ({reason})",
                        )
                    if _is_negative(stripped):
                        self._clear_pending_confirmation()
                        return CommandAction(
                            kind="error",
                            message="Okay. Ask again with the ticker or command you want.",
                        )
                    self._clear_pending_confirmation()

                from sadquant.tui_router import route_free_text

                decision = route_free_text(stripped, context_tickers=self.context_tickers)
                if decision.command is None:
                    self.pending_confirmation = decision.confirmation_command
                    self.pending_confirmation_reason = decision.reason if decision.confirmation_command is not None else None
                    return CommandAction(
                        kind="error",
                        message=decision.clarification or "I could not route that request. Try /help for explicit commands.",
                    )
                route_prefix = "Planned route" if self.plan_mode else "Routed to"
                return self._execute_or_plan(
                    decision.command,
                    message=f"{route_prefix}: sadquant {decision.command.display} ({decision.reason})",
                )
            try:
                args = parse_argument_line(stripped)
            except SlashCommandError as exc:
                return CommandAction(kind="error", message=str(exc))
            command = SlashCommand(name=self.active_command, args=_normalize_command_args(self.active_command, args), raw=stripped)
            return self._execute_or_plan(command)

        self._clear_pending_confirmation()
        try:
            command = parse_slash_command(stripped)
        except SlashCommandError as exc:
            return CommandAction(kind="error", message=str(exc))
        if command.native:
            return self._handle_native(command)

        if not command.args and command.name in MODE_COMMANDS:
            self.active_command = command.name
            return CommandAction(
                kind="mode",
                message=f"Entered {self.active_prompt} mode. Type arguments to run sadquant {command.name}, or /mode off.",
                command=command,
            )

        return self._execute_or_plan(command)

    def _execute_or_plan(self, command: SlashCommand, message: Optional[str] = None) -> CommandAction:
        if self.plan_mode:
            self.planned_command = command
            return CommandAction(
                kind="planned",
                message=message or f"Planned: sadquant {command.display}",
                command=command,
            )
        self._remember_command_context(command)
        return CommandAction(
            kind="execute",
            message=message or f"Running: sadquant {command.display}",
            command=command,
        )

    def _handle_native(self, command: SlashCommand) -> CommandAction:
        if command.name == "help":
            return CommandAction(kind="help", message=HELP_TEXT, command=command)
        if command.name == "clear":
            return CommandAction(kind="clear", message="Transcript cleared.", command=command)
        if command.name in {"exit", "quit"}:
            return CommandAction(kind="exit", message="Exiting SadQuant TUI.", command=command)
        if command.name == "exit-mode":
            return self._clear_active_mode(command)
        if command.name == "mode":
            requested = command.args[0].lower() if command.args else None
            if requested in {None, "off", "none", "normal"}:
                return self._clear_active_mode(command)
            if requested not in MODE_COMMANDS:
                return CommandAction(kind="error", message=f"Unknown command mode '{requested}'. Try /help.")
            self.active_command = requested
            return CommandAction(kind="mode", message=f"Entered {self.active_prompt} mode.", command=command)
        if command.name == "run":
            if self.planned_command is None:
                return CommandAction(kind="error", message="No planned command to run.")
            self._remember_command_context(self.planned_command)
            return CommandAction(kind="execute", message=f"Running planned command: sadquant {self.planned_command.display}", command=self.planned_command)
        if command.name == "plan":
            requested = command.args[0].lower() if command.args else None
            if requested in {"off", "false", "0", "normal"}:
                self.plan_mode = False
            elif requested in {"on", "true", "1"}:
                self.plan_mode = True
            elif requested is None:
                self.plan_mode = not self.plan_mode
            else:
                return CommandAction(kind="error", message="Use /plan, /plan on, or /plan off.")

            mode = "PLAN" if self.plan_mode else "NORMAL"
            return CommandAction(kind="plan", message=f"Mode: {mode}", command=command)

        return CommandAction(kind="error", message=f"Unhandled native command '/{command.name}'.")

    def _clear_active_mode(self, command: SlashCommand) -> CommandAction:
        if self.active_command is None:
            return CommandAction(kind="mode", message="No active command mode.", command=command)
        previous = self.active_command
        self.active_command = None
        return CommandAction(kind="mode", message=f"Left {previous}> mode.", command=command)

    def _clear_pending_confirmation(self) -> None:
        self.pending_confirmation = None
        self.pending_confirmation_reason = None

    def _remember_command_context(self, command: SlashCommand) -> None:
        tickers = _command_context_tickers(command)
        if tickers:
            self.context_tickers = tickers

    def suggestions(self, text: str) -> list[CommandSuggestion]:
        return suggestions_for(text, active_command=self.active_command)


def parse_argument_line(text: str) -> list[str]:
    try:
        return [_clean_token(token) for token in shlex.split(text, posix=False)]
    except ValueError as exc:
        raise SlashCommandError(f"Could not parse arguments: {exc}") from exc


def _normalize_command_args(command_name: str, args: list[str]) -> list[str]:
    meta = CLI_COMMAND_META.get(command_name)
    if meta is None:
        return args

    args = _expand_natural_option_aliases(command_name, args, meta)
    normalized: list[str] = []
    for arg in args:
        if not arg.startswith("-") or arg in meta.options:
            normalized.append(arg)
            continue
        matches = [option for option in meta.options if option.startswith(arg)]
        normalized.append(matches[0] if len(matches) == 1 else arg)
    return normalized


def _expand_natural_option_aliases(command_name: str, args: list[str], meta: CommandMeta) -> list[str]:
    if not args:
        return args
    args = _expand_universe_shorthand(command_name, args, meta)
    specs = _option_specs(meta)
    alias_map = _alias_map(specs)
    positional_floor = _positional_floor(command_name, args)
    expanded: list[str] = []
    positional_count = 0
    index = 0
    while index < len(args):
        arg = args[index]
        lowered = arg.lower()
        if arg.startswith("-"):
            expanded.append(arg)
            index += 1
            continue
        if lowered == "no" and index + 1 < len(args):
            next_spec = alias_map.get(args[index + 1].lower())
            if next_spec and next_spec.value_type == "bool":
                flag = next_spec.flag
                if flag.startswith("--no-"):
                    expanded.append(flag)
                index += 2
                continue
        spec = alias_map.get(lowered)
        if spec is not None and positional_count >= positional_floor:
            if spec.value_type == "bool":
                next_value = args[index + 1].lower() if index + 1 < len(args) else None
                if spec.flag.startswith("--no-"):
                    if next_value in {"off", "false", "no", "0"}:
                        expanded.append(spec.flag)
                        index += 2
                    elif next_value in {"on", "true", "yes", "1"}:
                        index += 2
                    else:
                        expanded.append(spec.flag)
                        index += 1
                else:
                    if next_value in {"off", "false", "no", "0"}:
                        index += 2
                    else:
                        expanded.append(spec.flag)
                        if next_value in {"on", "true", "yes", "1"}:
                            index += 2
                        else:
                            index += 1
                continue
            if index + 1 < len(args):
                expanded.extend([spec.flag, args[index + 1]])
                index += 2
                continue
        expanded.append(arg)
        if not arg.startswith("-"):
            positional_count += 1
        index += 1
    return expanded


def _expand_universe_shorthand(command_name: str, args: list[str], meta: CommandMeta) -> list[str]:
    if command_name not in {"scan", "screen"} or "--universe" not in meta.options:
        return args
    if not args or args[0].startswith("-"):
        return args
    alias_map = _alias_map(_option_specs(meta))
    if args[0].lower() in alias_map:
        return args
    return ["--universe", args[0], *args[1:]]


def _option_specs(meta: CommandMeta) -> tuple[OptionSpec, ...]:
    if meta.option_specs:
        return meta.option_specs
    specs = []
    for option in meta.options:
        specs.append(OPTION_SPEC_BY_FLAG.get(option, OptionSpec(option, (option.lstrip("-"),), description=f"{meta.name} option")))
    return tuple(specs)


def _alias_map(specs: tuple[OptionSpec, ...]) -> dict[str, OptionSpec]:
    aliases: dict[str, OptionSpec] = {}
    for spec in specs:
        aliases[spec.flag.lstrip("-").lower()] = spec
        for alias in spec.aliases:
            aliases[alias.lower()] = spec
    return aliases


def _positional_floor(command_name: str, args: list[str]) -> int:
    if command_name in {"analyze", "chart", "earnings", "fundamentals", "ingest-fmp", "insiders", "setup"}:
        return 1
    if command_name in {"ask", "ingest-note", "research"}:
        return 2
    if command_name in {"compare", "correlate"}:
        return 2
    if command_name == "eval":
        return 1
    if command_name == "signals":
        if args and args[0].lower() == "label":
            return 3
        return 1
    if command_name == "journal":
        return 1
    if command_name == "thesis":
        if args and args[0].lower() == "add":
            return 3
        return 1
    if command_name == "watchlist":
        if args and args[0].lower() in {"add", "remove"}:
            return 2
        if args and args[0].lower() == "show":
            return 2
        return 1
    return 0


def suggestions_for(text: str, active_command: Optional[str] = None) -> list[CommandSuggestion]:
    raw = text
    stripped = raw.lstrip()
    if stripped.startswith("/"):
        return _slash_suggestions(stripped)
    if active_command in CLI_COMMAND_META:
        return _argument_suggestions(raw, CLI_COMMAND_META[active_command], include_options=False)
    return []


def _slash_suggestions(text: str) -> list[CommandSuggestion]:
    body = text[1:]
    names = {**CLI_COMMAND_META, **NATIVE_COMMAND_META}
    if not body or (" " not in body and not body.endswith(" ")):
        prefix = body.lower()
        return [
            CommandSuggestion(value=f"/{name}", label=f"/{name}", description=meta.description)
            for name, meta in sorted(names.items())
            if name.startswith(prefix) and not (name == "compare" and prefix in {"c", "co", "com"})
        ]

    command_name, rest = body.split(" ", 1)
    command_name = command_name.lower()
    if command_name in CLI_COMMAND_META:
        if not rest and text.endswith(" "):
            rest = " "
        return _argument_suggestions(rest, CLI_COMMAND_META[command_name])
    if command_name == "mode":
        prefix = _current_token(rest).lower()
        mode_names = sorted([*MODE_COMMANDS, "off"])
        return [
            CommandSuggestion(value=name, label=name, description="Command mode" if name != "off" else "Leave command mode")
            for name in mode_names
            if name.startswith(prefix)
        ]
    if command_name == "plan":
        prefix = _current_token(rest).lower()
        return [
            CommandSuggestion(value=name, label=name, description="Plan mode setting")
            for name in ("on", "off")
            if name.startswith(prefix)
        ]
    return []


def _argument_suggestions(text: str, meta: CommandMeta, *, include_options: bool = True) -> list[CommandSuggestion]:
    token = _current_token(text)
    lower_token = token.lower()
    suggestions: list[CommandSuggestion] = []
    value_spec = _value_spec_for_current_position(text, meta) if include_options else None
    if value_spec is not None and value_spec.choices:
        return [
            CommandSuggestion(value=choice, label=choice, description=f"{value_spec.flag} value")
            for choice in value_spec.choices
            if choice.startswith(lower_token)
        ]
    if not text.strip() and meta.templates:
        suggestions.extend(_template_suggestions(meta))
    if text.endswith(" ") or not token:
        completed_count = _completed_argument_count(text)
        suggestions.extend(
            CommandSuggestion(
                value=hint.value,
                label=hint.label,
                description=hint.description,
                replace_token=hint.replace_token,
            )
            for hint in meta.parameter_suggestions
            if hint.after_args == completed_count
        )
    if meta.subcommands and (_is_first_argument(text) or not lower_token.startswith("-")):
        suggestions.extend(
            CommandSuggestion(value=subcommand, label=subcommand, description=f"{meta.name} subcommand")
            for subcommand in meta.subcommands
            if subcommand.startswith(lower_token)
        )
    if include_options and (token.startswith("-") or text.endswith(" ")):
        suggestions.extend(
            CommandSuggestion(value=option, label=option, description=f"{meta.name} option")
            for option in meta.options
            if option.startswith(token)
        )
    if include_options and not token.startswith("-"):
        suggestions.extend(
            CommandSuggestion(value=alias, label=alias, description=spec.description or f"{meta.name} option")
            for spec in _option_specs(meta)
            for alias in spec.aliases[:1]
            if alias.startswith(lower_token)
        )
    return suggestions


def _value_spec_for_current_position(text: str, meta: CommandMeta) -> Optional[OptionSpec]:
    try:
        tokens = [_clean_token(token) for token in shlex.split(text, posix=False)]
    except ValueError:
        tokens = text.strip().split()
    if not tokens:
        return None
    if not text.endswith(" "):
        tokens = tokens[:-1]
    if not tokens:
        return None
    previous = tokens[-1].lower()
    specs = _option_specs(meta)
    for spec in specs:
        if previous == spec.flag.lower() or previous in {alias.lower() for alias in spec.aliases}:
            return spec if spec.value_type != "bool" else None
    return None


def _template_suggestions(meta: CommandMeta) -> list[CommandSuggestion]:
    return [
        CommandSuggestion(
            value=template.value,
            label=template.label,
            description=template.description,
            replace_token=template.replace_token,
        )
        for template in meta.templates
    ]


def _completed_argument_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    try:
        tokens = shlex.split(stripped, posix=False)
    except ValueError:
        tokens = stripped.split()
    if text.endswith(" "):
        return len(tokens)
    return max(0, len(tokens) - 1)


def _current_token(text: str) -> str:
    if not text or text.endswith(" "):
        return ""
    return text.split()[-1]


def _is_first_argument(text: str) -> bool:
    stripped = text.strip()
    return not stripped or len(stripped.split()) == 1


def _is_affirmative(text: str) -> bool:
    return text.lower().strip() in {"y", "yes", "yeah", "yep", "sure", "ok", "okay", "correct", "right"}


def _is_negative(text: str) -> bool:
    return text.lower().strip() in {"n", "no", "nope", "nah", "cancel", "wrong"}


def _command_context_tickers(command: SlashCommand) -> list[str]:
    if command.name in {"analyze", "ask", "chart", "ingest-fmp", "ingest-note", "insiders", "research"}:
        return [_normalize_ticker(command.args[0])] if command.args and not command.args[0].startswith("-") else []
    if command.name == "correlate":
        tickers = []
        for arg in command.args:
            if arg.startswith("-"):
                break
            tickers.append(_normalize_ticker(arg))
        return tickers
    return []


def _normalize_ticker(value: str) -> str:
    return value.upper().strip()
