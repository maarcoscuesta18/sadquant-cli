from sadquant.tui import accept_suggestion
from sadquant.tui_bridge import TuiBridge
from sadquant.tui_commands import CommandSuggestion, SlashCommand, TuiCommandController, command_schema, compose_slash_command, parse_slash_command, suggestions_for
from sadquant.tui_router import RouteDecision


def test_parse_research_slash_command():
    command = parse_slash_command('/research NVDA "What changed?" --web')

    assert command.name == "research"
    assert command.args == ["NVDA", "What changed?", "--web"]
    assert command.argv == ["research", "NVDA", "What changed?", "--web"]
    assert not command.native


def test_parse_research_normalizes_unique_option_prefix():
    command = parse_slash_command('/research NVDA "What changed?" --agentic --finvi')

    assert command.argv == ["research", "NVDA", "What changed?", "--agentic", "--finviz"]


def test_parse_nested_eval_slash_command():
    command = parse_slash_command("/eval rag --dataset evals/rag.jsonl")

    assert command.argv == ["eval", "rag", "--dataset", "evals/rag.jsonl"]


def test_parse_nested_signals_slash_command():
    command = parse_slash_command("/signals journal --horizon swing")

    assert command.argv == ["signals", "journal", "--horizon", "swing"]


def test_plan_mode_plans_command_without_execution():
    controller = TuiCommandController()

    plan_action = controller.submit("/plan")
    planned_action = controller.submit('/research NVDA "What changed?" --web')

    assert plan_action.kind == "plan"
    assert controller.plan_mode
    assert planned_action.kind == "planned"
    assert planned_action.command is not None
    assert planned_action.command.argv == ["research", "NVDA", "What changed?", "--web"]


def test_bare_command_enters_mode_without_execution():
    controller = TuiCommandController()

    action = controller.submit("/chart")

    assert action.kind == "mode"
    assert controller.active_command == "chart"
    assert controller.active_prompt == "chart>"


def test_plain_text_executes_active_command_mode():
    controller = TuiCommandController()
    controller.submit("/chart")

    action = controller.submit("NVDA --period 6mo")

    assert action.kind == "execute"
    assert action.command is not None
    assert action.command.argv == ["chart", "NVDA", "--period", "6mo"]


def test_active_mode_normalizes_unique_option_prefix():
    controller = TuiCommandController()
    controller.submit("/research")

    action = controller.submit('NVDA "What changed?" --finvi')

    assert action.kind == "execute"
    assert action.command is not None
    assert action.command.argv == ["research", "NVDA", "What changed?", "--finviz"]


def test_slash_command_with_args_is_one_shot_and_does_not_enter_mode():
    controller = TuiCommandController()

    action = controller.submit("/chart NVDA")

    assert action.kind == "execute"
    assert action.command is not None
    assert action.command.argv == ["chart", "NVDA"]
    assert controller.active_command is None


def test_mode_off_and_exit_mode_clear_active_mode():
    controller = TuiCommandController()
    controller.submit("/chart")

    mode_off = controller.submit("/mode off")
    controller.submit("/research")
    exit_mode = controller.submit("/exit-mode")

    assert mode_off.kind == "mode"
    assert mode_off.message == "Left chart> mode."
    assert exit_mode.kind == "mode"
    assert exit_mode.message == "Left research> mode."
    assert controller.active_command is None


def test_plan_mode_plans_plain_text_in_active_command_mode():
    controller = TuiCommandController()
    controller.submit("/chart")
    controller.submit("/plan")

    action = controller.submit("NVDA --period 6mo")

    assert action.kind == "planned"
    assert action.command is not None
    assert action.command.argv == ["chart", "NVDA", "--period", "6mo"]


def test_run_executes_latest_planned_command():
    controller = TuiCommandController()
    controller.submit("/plan")
    controller.submit("/scan --universe semis --top 5")

    action = controller.submit("/run")

    assert action.kind == "execute"
    assert action.command is not None
    assert action.command.argv == ["scan", "--universe", "semis", "--top", "5"]
    assert controller.plan_mode


def test_plan_off_returns_to_normal_mode():
    controller = TuiCommandController()
    controller.submit("/plan")

    action = controller.submit("/plan off")
    execute_action = controller.submit("/providers")

    assert action.kind == "plan"
    assert not controller.plan_mode
    assert execute_action.kind == "execute"


def test_slash_autocomplete_suggests_research():
    suggestions = suggestions_for("/re")

    assert [suggestion.value for suggestion in suggestions] == ["/research"]


def test_chart_mode_autocomplete_excludes_options():
    suggestions = suggestions_for("--p", active_command="chart")

    assert "--period" not in [suggestion.value for suggestion in suggestions]


def test_eval_autocomplete_suggests_subcommands():
    suggestions = suggestions_for("/eval ")

    assert {"rag", "signals", "returns"}.issubset({suggestion.value for suggestion in suggestions})


def test_new_investor_commands_parse_and_suggest():
    assert parse_slash_command("/setup NVDA --horizon swing").argv == ["setup", "NVDA", "--horizon", "swing"]
    assert parse_slash_command("/screen --universe semis --recipe momentum").argv == ["screen", "--universe", "semis", "--recipe", "momentum"]
    assert parse_slash_command("/watchlist add semis NVDA AMD").argv == ["watchlist", "add", "semis", "NVDA", "AMD"]
    assert "/compare" in [suggestion.value for suggestion in suggestions_for("/comp")]


def test_natural_option_aliases_compile_to_cli_flags():
    assert parse_slash_command("/setup NVDA horizon swing journal").argv == [
        "setup",
        "NVDA",
        "--horizon",
        "swing",
        "--journal-signal",
    ]
    assert parse_slash_command("/screen semis recipe momentum top 10").argv == [
        "screen",
        "--universe",
        "semis",
        "--recipe",
        "momentum",
        "--top",
        "10",
    ]
    assert parse_slash_command('/research NVDA "what changed" web finviz agentic').argv == [
        "research",
        "NVDA",
        "what changed",
        "--web",
        "--finviz",
        "--agentic",
    ]
    assert parse_slash_command("/analyze NVDA ai off").argv == [
        "analyze",
        "NVDA",
        "--no-ai",
    ]
    assert parse_slash_command("/chart NVDA period 6mo interval 1d volume off").argv == [
        "chart",
        "NVDA",
        "--period",
        "6mo",
        "--interval",
        "1d",
        "--no-volume",
    ]


def test_nested_natural_option_aliases_compile_to_cli_flags():
    assert parse_slash_command("/eval returns horizon swing").argv == ["eval", "returns", "--horizon", "swing"]
    assert parse_slash_command("/thesis add NVDA thesis horizon position").argv == ["thesis", "add", "NVDA", "thesis", "--horizon", "position"]
    assert parse_slash_command("/watchlist show semis format json").argv == ["watchlist", "show", "semis", "--format", "json"]


def test_option_alias_suggestions_include_choices():
    assert "horizon" in [suggestion.value for suggestion in suggestions_for("/setup NVDA h")]
    assert {"swing", "position", "intraday"}.issubset({suggestion.value for suggestion in suggestions_for("/setup NVDA horizon ")})
    assert {"momentum", "vcp"}.issubset({suggestion.value for suggestion in suggestions_for("/screen recipe ")})


def test_command_schema_and_compose_command_expose_structured_options():
    schema = command_schema("setup")
    horizon = next(option for option in schema["options"] if option["flag"] == "--horizon")
    command = compose_slash_command("setup", ["NVDA", "horizon", "position", "journal"])

    assert "horizon" in horizon["aliases"]
    assert "position" in horizon["choices"]
    assert command.argv == ["setup", "NVDA", "--horizon", "position", "--journal-signal"]


def test_unknown_autocomplete_prefix_returns_no_suggestions():
    assert suggestions_for("/zz") == []


def test_tui_bridge_exposes_initial_state():
    bridge = TuiBridge()

    response = bridge.handle({"type": "hello"})

    assert response["ok"]
    assert response["state"]["modeLabel"] == "NORMAL"
    assert response["state"]["activePrompt"] == "/"


def test_accepting_slash_command_suggestion_keeps_input_editable():
    suggestion = suggestions_for("/co")[0]

    accepted = accept_suggestion("/co", suggestion)

    assert accepted.text == "/correlate "
    assert accepted.cursor_position == len("/correlate ")


def test_accepting_option_suggestion_adds_space_for_value():
    suggestion = CommandSuggestion(value="--period", label="--period", description="correlate option")

    accepted = accept_suggestion("/correlate NVDA AMD --p", suggestion)

    assert accepted.text == "/correlate NVDA AMD --period "


def test_correlate_options_are_suggested_after_command_insert():
    suggestions = suggestions_for("/correlate ")

    assert {"--period", "--provider", "--model", "--no-ai"}.issubset({suggestion.value for suggestion in suggestions})


def test_research_suggestions_include_prompt_templates():
    suggestions = suggestions_for("/research ")

    values = [suggestion.value for suggestion in suggestions]
    assert 'NVDA "What changed in earnings, guidance, estimates, and price action?" --web --finviz' in values


def test_research_suggestions_show_question_after_ticker():
    suggestions = suggestions_for("/research NVDA ")

    labels = {suggestion.label for suggestion in suggestions}
    assert "research prompt" in labels
    assert "scenario prompt" in labels


def test_active_mode_suggestions_show_question_after_ticker():
    suggestions = suggestions_for("NVDA ", active_command="research")

    assert "research prompt" in {suggestion.label for suggestion in suggestions}


def test_active_mode_suggestions_exclude_options_and_option_values():
    assert "--web" not in [suggestion.value for suggestion in suggestions_for("NVDA question ", active_command="research")]
    assert "web" not in [suggestion.value for suggestion in suggestions_for("NVDA question w", active_command="research")]
    assert "swing" not in [suggestion.value for suggestion in suggestions_for("NVDA question horizon ", active_command="research")]


def test_accepting_append_suggestion_keeps_existing_input():
    suggestion = CommandSuggestion(
        value='"What changed?"',
        label="research prompt",
        description="Question prompt",
        replace_token=False,
    )

    accepted = accept_suggestion("/research NVDA", suggestion)

    assert accepted.text == '/research NVDA "What changed?" '


def test_tui_bridge_returns_suggestions():
    bridge = TuiBridge()

    response = bridge.handle({"type": "suggestions", "text": "/co"})

    assert response["ok"]
    assert response["suggestions"] == [
        {
            "value": "/correlate",
            "label": "/correlate",
            "description": "Show a return correlation matrix for tickers.",
            "replaceToken": True,
        }
    ]


def test_tui_bridge_accepts_suggestion():
    bridge = TuiBridge()
    suggestion = bridge.handle({"type": "suggestions", "text": "/co"})["suggestions"][0]

    response = bridge.handle({"type": "accept_suggestion", "text": "/co", "suggestion": suggestion})

    assert response["ok"]
    assert response["accepted"] == {"text": "/correlate ", "cursor_position": len("/correlate ")}


def test_tui_bridge_exposes_schema_and_composes_natural_aliases():
    bridge = TuiBridge()

    schema = bridge.handle({"type": "command_schema", "command": "setup"})
    composed = bridge.handle({"type": "compose_command", "command": "setup", "args": ["NVDA", "horizon", "swing", "journal"]})

    assert schema["ok"]
    assert any(option["flag"] == "--horizon" for option in schema["schema"]["options"])
    assert composed["ok"]
    assert composed["command"]["argv"] == ["setup", "NVDA", "--horizon", "swing", "--journal-signal"]


def test_tui_bridge_submit_preserves_plan_state():
    bridge = TuiBridge()

    bridge.handle({"type": "submit", "text": "/plan"})
    response = bridge.handle({"type": "submit", "text": "/scan --universe semis --top 5"})

    assert response["ok"]
    assert response["action"]["kind"] == "planned"
    assert response["state"]["modeLabel"] == "PLAN"
    assert response["state"]["plannedCommand"]["argv"] == ["scan", "--universe", "semis", "--top", "5"]


def test_tui_bridge_run_returns_execute_action_for_latest_plan():
    bridge = TuiBridge()

    bridge.handle({"type": "submit", "text": "/plan"})
    bridge.handle({"type": "submit", "text": "/providers"})
    response = bridge.handle({"type": "submit", "text": "/run"})

    assert response["ok"]
    assert response["action"]["kind"] == "execute"
    assert response["action"]["command"]["argv"] == ["providers"]


def test_tui_bridge_reports_errors_as_actions():
    bridge = TuiBridge()

    response = bridge.handle({"type": "submit", "text": "NVDA"})

    assert response["ok"]
    assert response["action"]["kind"] == "error"
    assert "What should I do with NVDA" in response["action"]["message"]


def test_root_free_text_auto_routes_to_execute():
    bridge = TuiBridge()

    response = bridge.handle({"type": "submit", "text": "what changed for NVDA today?"})

    assert response["ok"]
    assert response["action"]["kind"] == "execute"
    assert response["action"]["message"].startswith("Routed to: sadquant research")
    assert response["action"]["command"]["argv"] == [
        "research",
        "NVDA",
        "what changed for NVDA today?",
        "--agentic",
        "--web",
        "--horizon",
        "intraday",
    ]


def test_plan_mode_plans_root_free_text_route():
    bridge = TuiBridge()

    bridge.handle({"type": "submit", "text": "/plan"})
    response = bridge.handle({"type": "submit", "text": "chart NVDA"})

    assert response["ok"]
    assert response["action"]["kind"] == "planned"
    assert response["action"]["message"].startswith("Planned route: sadquant chart")
    assert response["state"]["plannedCommand"]["argv"] == ["chart", "NVDA"]


def test_free_text_follow_up_uses_last_command_ticker():
    controller = TuiCommandController()

    first = controller.submit("what is SNDK doing today")
    follow_up = controller.submit("tell me about earnings and what to expect of today's earnings")

    assert first.kind == "execute"
    assert follow_up.kind == "execute"
    assert follow_up.command is not None
    assert follow_up.command.argv == [
        "research",
        "SNDK",
        "tell me about earnings and what to expect of today's earnings",
        "--agentic",
        "--web",
        "--finviz",
        "--horizon",
        "intraday",
    ]


def test_yes_confirms_pending_routed_clarification(monkeypatch):
    command = SlashCommand(name="research", args=["INTC", "how is it intel today", "--agentic", "--web"], raw="how is it intel today")

    def fake_route_free_text(text, **kwargs):
        return RouteDecision(
            command=None,
            reason="Intel maps to INTC",
            clarification="Do you mean Intel stock ticker INTC?",
            confirmation_command=command,
        )

    monkeypatch.setattr("sadquant.tui_router.route_free_text", fake_route_free_text)
    controller = TuiCommandController()

    clarification = controller.submit("how is it intel today")
    action = controller.submit("yes")

    assert clarification.kind == "error"
    assert "INTC" in clarification.message
    assert action.kind == "execute"
    assert action.command is not None
    assert action.command.argv == ["research", "INTC", "how is it intel today", "--agentic", "--web"]


def test_no_clears_pending_routed_clarification(monkeypatch):
    command = SlashCommand(name="research", args=["INTC", "how is it intel today", "--agentic", "--web"], raw="how is it intel today")

    def fake_route_free_text(text, **kwargs):
        return RouteDecision(
            command=None,
            reason="Intel maps to INTC",
            clarification="Do you mean Intel stock ticker INTC?",
            confirmation_command=command,
        )

    monkeypatch.setattr("sadquant.tui_router.route_free_text", fake_route_free_text)
    controller = TuiCommandController()

    controller.submit("how is it intel today")
    action = controller.submit("no")

    assert action.kind == "error"
    assert "Okay" in action.message
    assert controller.pending_confirmation is None
