from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model: str
    text: str


StatusCallback = Callable[[str], None]


class BaseModelClient:
    provider = "base"

    def available(self) -> bool:
        raise NotImplementedError

    def complete(self, prompt: str, instructions: str, on_status: Optional[StatusCallback] = None) -> ModelResponse:
        raise NotImplementedError


class ResponsesModel:
    """Responses API adapter for OpenAI-compatible providers."""

    provider = "responses"

    def __init__(
        self,
        provider: str,
        api_key_env: str,
        default_model: str,
        base_url: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model = model or os.getenv("SADQUANT_MODEL") or os.getenv(f"SADQUANT_{provider.upper()}_MODEL", default_model)
        self.api_key_env = api_key_env
        self.api_key = api_key or os.getenv(api_key_env)
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, instructions: str, on_status: Optional[StatusCallback] = None) -> ModelResponse:
        if not self.api_key:
            raise ModelError(f"{self.api_key_env} is not set.")

        _emit_status(on_status, f"Calling {self.provider}:{self.model}")
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": prompt,
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data.get("output_text")
        if not text:
            text = _extract_output_text(data)
        if not text:
            raise ModelError("OpenAI response did not include text output.")

        _emit_status(on_status, f"Received {self.provider} response")
        return ModelResponse(provider=self.provider, model=self.model, text=text)


class OpenAIModel(ResponsesModel):
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        super().__init__(
            provider="openai",
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-5.5",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=model,
            api_key=api_key,
        )


class GroqModel(ResponsesModel):
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        super().__init__(
            provider="groq",
            api_key_env="GROQ_API_KEY",
            default_model="openai/gpt-oss-20b",
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            model=model,
            api_key=api_key,
        )


class GeminiModel(BaseModelClient):
    provider = "gemini"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or os.getenv("SADQUANT_MODEL") or os.getenv("SADQUANT_GEMINI_MODEL", "gemini-2.5-pro")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, instructions: str, on_status: Optional[StatusCallback] = None) -> ModelResponse:
        if not self.api_key:
            raise ModelError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")

        _emit_status(on_status, f"Calling {self.provider}:{self.model}")
        payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        with httpx.Client(timeout=60) as client:
            response = client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

        text = _extract_gemini_text(data)
        if not text:
            raise ModelError("Gemini response did not include text output.")
        _emit_status(on_status, f"Received {self.provider} response")
        return ModelResponse(provider=self.provider, model=self.model, text=text)


class AnthropicModel(BaseModelClient):
    provider = "anthropic"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or os.getenv("SADQUANT_MODEL") or os.getenv("SADQUANT_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, instructions: str, on_status: Optional[StatusCallback] = None) -> ModelResponse:
        if not self.api_key:
            raise ModelError("ANTHROPIC_API_KEY is not set.")

        _emit_status(on_status, f"Calling {self.provider}:{self.model}")
        payload = {
            "model": self.model,
            "max_tokens": 1600,
            "system": instructions,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = _extract_anthropic_text(data)
        if not text:
            raise ModelError("Anthropic response did not include text output.")
        _emit_status(on_status, f"Received {self.provider} response")
        return ModelResponse(provider=self.provider, model=self.model, text=text)


class ExternalCliModel(BaseModelClient):
    provider = "cli"

    def __init__(self, command: Optional[str] = None, model: Optional[str] = None) -> None:
        self.command = command or os.getenv("SADQUANT_CLI_COMMAND")
        self.model = model or os.getenv("SADQUANT_MODEL") or self.command or "external-cli"

    def available(self) -> bool:
        if not self.command:
            return False
        try:
            _resolve_command_args(self.command)
        except ModelError:
            return False
        return True

    def complete(self, prompt: str, instructions: str, on_status: Optional[StatusCallback] = None) -> ModelResponse:
        if not self.command:
            raise ModelError("SADQUANT_CLI_COMMAND is not set.")

        full_prompt = f"{instructions}\n\n{prompt}"
        args = _resolve_command_args(self.command)
        _emit_status(on_status, f"Starting external model command {self.model}")
        try:
            result = subprocess.run(
                args,
                input=full_prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=int(os.getenv("SADQUANT_CLI_TIMEOUT", "180")),
                check=False,
            )
        except FileNotFoundError as exc:
            raise ModelError(f"External CLI executable not found: {args[0]}") from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "no stderr"
            raise ModelError(f"External CLI model failed with exit code {result.returncode}: {stderr}")

        text = (result.stdout or "").strip()
        if not text:
            raise ModelError("External CLI model returned empty stdout.")
        _emit_status(on_status, f"Received {self.provider} response")
        return ModelResponse(provider=self.provider, model=self.model, text=text)


class CodexCliModel(ExternalCliModel):
    provider = "codex"

    def __init__(self, model: Optional[str] = None) -> None:
        command = os.getenv("SADQUANT_CODEX_COMMAND")
        if not command:
            model_arg = model or os.getenv("SADQUANT_MODEL")
            model_flags = f" --model {shlex.quote(model_arg)}" if model_arg else ""
            command = f"codex exec --skip-git-repo-check --color never{model_flags} -"
        super().__init__(command=command, model=model or os.getenv("SADQUANT_MODEL") or "codex-cli")
        self.provider = "codex"


def create_model(provider: Optional[str] = None, model: Optional[str] = None) -> BaseModelClient:
    selected = (provider or os.getenv("SADQUANT_AI_PROVIDER", "codex")).lower().strip()
    if selected == "openai":
        return OpenAIModel(model=model)
    if selected == "groq":
        return GroqModel(model=model)
    if selected in {"gemini", "google"}:
        return GeminiModel(model=model)
    if selected in {"anthropic", "claude"}:
        return AnthropicModel(model=model)
    if selected in {"cli", "external-cli", "subscription"}:
        return ExternalCliModel(model=model)
    if selected == "codex":
        return CodexCliModel(model=model)
    raise ModelError(f"Unknown AI provider '{selected}'. Use openai, groq, gemini, anthropic, codex, or cli.")


def _resolve_command_args(command: str) -> list[str]:
    args = shlex.split(command, posix=os.name != "nt")
    if not args:
        raise ModelError("External CLI command is empty.")

    executable = args[0].strip("\"")
    resolved = _resolve_executable(executable)
    if not resolved:
        raise ModelError(f"External CLI executable not found: {executable}")
    args[0] = resolved
    return args


def _resolve_executable(executable: str) -> Optional[str]:
    if os.path.dirname(executable):
        return executable if os.path.exists(executable) else None

    if os.name == "nt" and not os.path.splitext(executable)[1]:
        resolved_exe = shutil.which(f"{executable}.exe")
        if resolved_exe:
            return resolved_exe

    return shutil.which(executable)


def _extract_output_text(data: dict) -> str:
    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _extract_gemini_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if part.get("text"):
                parts.append(part["text"])
    return "\n".join(parts).strip()


def _extract_anthropic_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in data.get("content", []):
        if item.get("type") == "text" and item.get("text"):
            parts.append(item["text"])
    return "\n".join(parts).strip()


def _emit_status(on_status: Optional[StatusCallback], message: str) -> None:
    if on_status is not None:
        on_status(message)


def fallback_synthesis(prompt: str) -> ModelResponse:
    return ModelResponse(
        provider="local-fallback",
        model="none",
        text=(
            "OPENAI_API_KEY is not set, so no AI synthesis was generated.\n\n"
            "Tool-backed research packet:\n\n"
            f"{prompt}"
        ),
    )
