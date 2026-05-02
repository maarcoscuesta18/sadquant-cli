import pytest

from sadquant.ai import ModelResponse
from sadquant.tui_router import route_free_text, validate_routed_command


class FakeModel:
    provider = "fake"
    model = "fake-router"

    def __init__(self, text):
        self.text = text

    def available(self):
        return True

    def complete(self, prompt, instructions, on_status=None):
        if on_status is not None:
            on_status(f"Calling {self.provider}:{self.model}")
        return ModelResponse(provider=self.provider, model=self.model, text=self.text)


class UnavailableModel:
    def available(self):
        return False

    def complete(self, prompt, instructions, on_status=None):
        raise AssertionError("complete should not be called")


def test_rule_routes_chart_request():
    decision = route_free_text("chart NVDA 6mo")

    assert decision.command is not None
    assert decision.command.argv == ["chart", "NVDA", "--period", "6mo"]
    assert "chart" in decision.reason


def test_rule_routes_scan_request_with_universe_and_top():
    decision = route_free_text("scan semis top 5")

    assert decision.command is not None
    assert decision.command.argv == ["scan", "--universe", "semis", "--top", "5"]


def test_rule_routes_correlate_request():
    decision = route_free_text("compare NVDA vs AMD")

    assert decision.command is not None
    assert decision.command.argv == ["correlate", "NVDA", "AMD"]


def test_rule_routes_compare_request_without_correlation_language():
    decision = route_free_text("compare NVDA AMD AVGO fundamentals and risk")

    assert decision.command is not None
    assert decision.command.argv == ["compare", "NVDA", "AMD", "AVGO"]


def test_rule_routes_setup_and_named_screen_requests():
    setup = route_free_text("build a swing setup for NVDA with invalidation")
    screen = route_free_text("screen semis top 5 momentum")

    assert setup.command is not None
    assert setup.command.argv == ["setup", "NVDA", "--horizon", "swing"]
    assert screen.command is not None
    assert screen.command.argv == ["screen", "--universe", "semis", "--recipe", "momentum", "--top", "5"]


def test_rule_routes_broad_research_request_with_flags():
    decision = route_free_text("what changed for NVDA today?")

    assert decision.command is not None
    assert decision.command.argv == [
        "research",
        "NVDA",
        "what changed for NVDA today?",
        "--agentic",
        "--web",
        "--horizon",
        "intraday",
    ]


def test_company_alias_routes_intel_to_intc():
    decision = route_free_text("how is it intel today")

    assert decision.command is not None
    assert decision.command.argv == [
        "research",
        "INTC",
        "how is it intel today",
        "--agentic",
        "--web",
        "--horizon",
        "intraday",
    ]


def test_rule_routes_local_context_to_hybrid_ask():
    decision = route_free_text("what do my notes say about NVDA risks?")

    assert decision.command is not None
    assert decision.command.argv == ["ask", "NVDA", "what do my notes say about NVDA risks?", "--hybrid"]


def test_follow_up_uses_context_ticker_instead_of_imperative_word():
    decision = route_free_text("tell me about earnings and what to expect of today's earnings", context_tickers=["SNDK"])

    assert decision.command is not None
    assert decision.command.argv == [
        "research",
        "SNDK",
        "tell me about earnings and what to expect of today's earnings",
        "--agentic",
        "--web",
        "--finviz",
        "--horizon",
        "intraday",
    ]


def test_normal_prose_does_not_create_single_letter_ticker():
    decision = route_free_text("tell me about today's earnings", model=UnavailableModel())

    assert decision.command is None
    assert decision.clarification is not None


def test_explicit_cashtag_can_route_single_letter_ticker():
    decision = route_free_text("what changed for $F today", model=UnavailableModel())

    assert decision.command is not None
    assert decision.command.argv == [
        "research",
        "F",
        "what changed for $F today",
        "--agentic",
        "--web",
        "--horizon",
        "intraday",
    ]


def test_bare_ticker_returns_clarification_without_model():
    decision = route_free_text("NVDA", model=UnavailableModel())

    assert decision.command is None
    assert decision.clarification is not None
    assert "What should I do with NVDA" in decision.clarification


def test_llm_router_fallback_uses_strict_json():
    model = FakeModel('{"command":"analyze","args":["MSFT"],"reason":"score request","clarification":null}')

    decision = route_free_text("quick view MSFT", model=model)

    assert decision.command is not None
    assert decision.command.argv == ["analyze", "MSFT"]
    assert decision.reason == "score request"


def test_llm_router_emits_status_updates():
    model = FakeModel('{"command":"analyze","args":["MSFT"],"reason":"score request","clarification":null}')
    messages: list[str] = []

    decision = route_free_text("quick view MSFT", model=model, on_status=messages.append)

    assert decision.command is not None
    assert messages == [
        "Routing with fake:fake-router",
        "Calling fake:fake-router",
    ]


def test_llm_router_clarification_does_not_execute():
    model = FakeModel('{"command":null,"args":[],"reason":"missing ticker","clarification":"Which ticker?"}')

    decision = route_free_text("what changed today?", model=model)

    assert decision.command is None
    assert decision.clarification == "Which ticker?"


def test_llm_router_clarification_can_carry_confirmation_command():
    model = FakeModel(
        '{"command":"research","args":["INTC","how is it intel today","--agentic","--web"],'
        '"reason":"Intel maps to INTC","clarification":"Do you mean Intel stock ticker INTC?"}'
    )

    decision = route_free_text("quick view bluechip", model=model)

    assert decision.command is None
    assert decision.confirmation_command is not None
    assert decision.confirmation_command.argv == ["research", "INTC", "how is it intel today", "--agentic", "--web"]


def test_validation_rejects_unknown_command():
    with pytest.raises(ValueError, match="unknown"):
        validate_routed_command("shell", ["echo", "bad"], "bad")


def test_validation_rejects_unsupported_option():
    with pytest.raises(ValueError, match="unsupported option"):
        validate_routed_command("research", ["NVDA", "question", "--bad"], "bad")
