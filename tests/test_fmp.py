import pytest
from typer.testing import CliRunner

from sadquant.fmp import ingest_fmp_context
from sadquant.cli import app
from sadquant.providers import FmpProvider, FmpProviderError
from sadquant.rag import RagStore
from sadquant.tools import default_registry


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else [{"ok": True}]

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("unexpected raise_for_status call")


def test_fmp_provider_uses_query_auth_and_base_url(monkeypatch, tmp_path):
    captured = {}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params):
            captured["url"] = url
            captured["params"] = params
            return FakeResponse(payload={"result": "ok"})

    monkeypatch.setattr("sadquant.providers.httpx.Client", FakeClient)

    provider = FmpProvider(api_key="secret", base_url="https://example.test/stable", cache_dir=tmp_path)
    payload = provider.get("quote", {"symbol": "NVDA"}, cache_ttl=300)

    assert payload == {"result": "ok"}
    assert captured["url"] == "https://example.test/stable/quote"
    assert captured["params"] == {"symbol": "NVDA", "apikey": "secret"}


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (403, "Check FMP_API_KEY"),
        (429, "rate limit"),
    ],
)
def test_fmp_provider_reports_auth_and_rate_limit_errors(monkeypatch, status_code, message):
    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params):
            return FakeResponse(status_code=status_code)

    monkeypatch.setattr("sadquant.providers.httpx.Client", FakeClient)

    with pytest.raises(FmpProviderError, match=message):
        FmpProvider(api_key="secret").get("quote", {"symbol": "NVDA"})


def test_fmp_provider_reads_from_cache(monkeypatch, tmp_path):
    calls = {"count": 0}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params):
            calls["count"] += 1
            return FakeResponse(payload={"count": calls["count"]})

    monkeypatch.setattr("sadquant.providers.httpx.Client", FakeClient)
    provider = FmpProvider(api_key="secret", cache_dir=tmp_path)

    assert provider.get("quote", {"symbol": "NVDA"}, cache_ttl=300) == {"count": 1}
    assert provider.get("quote", {"symbol": "NVDA"}, cache_ttl=300) == {"count": 1}
    assert calls["count"] == 1


def test_fmp_tools_are_registered_and_normalize_payloads(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    monkeypatch.setattr("sadquant.tools.fmp_market_context", lambda ticker, provider: {"ticker": ticker})
    monkeypatch.setattr("sadquant.tools.fmp_fundamentals_context", lambda ticker, provider: {"profile": {"symbol": ticker}})
    monkeypatch.setattr("sadquant.tools.fmp_estimates_context", lambda ticker, provider: {"estimates": []})
    monkeypatch.setattr("sadquant.tools.fmp_catalysts_context", lambda ticker, provider=None: {"news": []})
    monkeypatch.setattr("sadquant.tools.fmp_transcripts_context", lambda ticker, provider: {"selected_transcript": None})
    monkeypatch.setattr("sadquant.tools.fmp_insiders_context", lambda ticker, provider: {"statistics": []})
    monkeypatch.setattr("sadquant.tools.fmp_signal_context", lambda ticker, provider: {"signal": "NEUTRAL"})

    registry = default_registry()

    for name in [
        "fmp_market",
        "fmp_fundamentals",
        "fmp_estimates",
        "fmp_catalysts",
        "fmp_transcripts",
        "fmp_insiders",
        "fmp_signal_context",
    ]:
        result = registry.run(name, "NVDA", "deep report")
        assert result.name == name
        assert result.source in {"fmp", "fmp+yfinance"}
        assert result.data


def test_ingest_fmp_writes_news_press_releases_and_transcripts_to_rag(tmp_path):
    class FakeProvider:
        def get(self, path, params=None, cache_ttl=None):
            if path == "news/stock":
                return [{"title": "AI demand", "text": "NVDA AI demand accelerated.", "publishedDate": "2026-04-01"}]
            if path == "news/press-releases":
                return [{"title": "Product update", "text": "NVDA announced a platform update.", "publishedDate": "2026-04-02"}]
            if path == "earning-call-transcript-latest":
                return [{"symbol": "NVDA", "year": 2025, "quarter": 4}]
            if path == "earning-call-transcript":
                return [{"symbol": "NVDA", "year": 2025, "quarter": 4, "content": "Management discussed AI demand and margins."}]
            raise AssertionError(f"unexpected path {path}")

    store = RagStore(tmp_path / "rag.sqlite")
    count = ingest_fmp_context(
        "NVDA",
        include_news=True,
        include_press_releases=True,
        include_transcripts=True,
        limit=1,
        provider=FakeProvider(),
        store=store,
    )

    assert count == 3
    matches = store.search("NVDA", "AI", limit=5)
    assert {doc.source for doc in matches} >= {"fmp:news", "fmp:transcript"}


def test_providers_command_reports_fmp_status(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    monkeypatch.setenv("FMP_BASE_URL", "https://example.test/stable")

    result = CliRunner().invoke(app, ["providers"])

    assert result.exit_code == 0
    assert "fmp" in result.output
    assert "https://example.test/stable" in result.output
