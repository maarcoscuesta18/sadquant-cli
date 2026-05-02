from subprocess import CompletedProcess

import pytest

from sadquant.ai import (
    ExternalCliModel,
    ModelError,
    _extract_anthropic_text,
    _extract_gemini_text,
    _resolve_executable,
    create_model,
)


def test_create_model_defaults_to_codex(monkeypatch):
    monkeypatch.delenv("SADQUANT_AI_PROVIDER", raising=False)
    assert create_model().provider == "codex"


def test_create_model_selects_supported_providers():
    assert create_model("openai").provider == "openai"
    assert create_model("groq").provider == "groq"
    assert create_model("gemini").provider == "gemini"
    assert create_model("anthropic").provider == "anthropic"
    assert create_model("codex").provider == "codex"
    assert create_model("cli").provider == "cli"


def test_external_cli_unavailable_when_executable_is_missing(monkeypatch):
    monkeypatch.setattr("sadquant.ai.shutil.which", lambda executable: None)
    assert not ExternalCliModel(command="missing-command").available()


def test_resolve_executable_prefers_windows_exe(monkeypatch):
    calls = []

    def fake_which(executable):
        calls.append(executable)
        if executable == "codex.exe":
            return r"C:\Tools\codex.exe"
        if executable == "codex":
            return r"C:\Tools\codex.CMD"
        return None

    monkeypatch.setattr("sadquant.ai.os.name", "nt")
    monkeypatch.setattr("sadquant.ai.shutil.which", fake_which)

    assert _resolve_executable("codex") == r"C:\Tools\codex.exe"
    assert calls == ["codex.exe"]


def test_external_cli_decodes_output_as_utf8(monkeypatch):
    captured = {}
    statuses = []

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("sadquant.ai._resolve_command_args", lambda command: ["model-cli"])
    monkeypatch.setattr("sadquant.ai.subprocess.run", fake_run)

    response = ExternalCliModel(command="model-cli", model="model-cli").complete("prompt", "instructions", on_status=statuses.append)

    assert response.text == "ok"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert statuses == ["Starting external model command model-cli", "Received cli response"]


def test_external_cli_handles_missing_output_streams(monkeypatch):
    def fake_run(*args, **kwargs):
        return CompletedProcess(args=args[0], returncode=1, stdout=None, stderr=None)

    monkeypatch.setattr("sadquant.ai._resolve_command_args", lambda command: ["model-cli"])
    monkeypatch.setattr("sadquant.ai.subprocess.run", fake_run)

    with pytest.raises(ModelError, match="no stderr"):
        ExternalCliModel(command="model-cli").complete("prompt", "instructions")


def test_extract_gemini_text():
    data = {"candidates": [{"content": {"parts": [{"text": "hello"}, {"text": "world"}]}}]}
    assert _extract_gemini_text(data) == "hello\nworld"


def test_extract_anthropic_text():
    data = {"content": [{"type": "text", "text": "hello"}, {"type": "tool_use", "name": "ignored"}]}
    assert _extract_anthropic_text(data) == "hello"
