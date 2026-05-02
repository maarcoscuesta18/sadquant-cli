from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from sadquant.tui_commands import CommandSuggestion


class InkTuiMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class AcceptedSuggestion:
    text: str
    cursor_position: int


def accept_suggestion(text: str, suggestion: CommandSuggestion) -> AcceptedSuggestion:
    """Return input text after accepting a completion suggestion."""
    value = suggestion.value
    if suggestion.replace_token:
        token = _current_token(text)
        start = len(text) - len(token) if token else len(text)
        accepted = f"{text[:start]}{value}{text[len(text):]}"
    else:
        separator = "" if not text or text.endswith(" ") else " "
        accepted = f"{text}{separator}{value}"
    if accepted and not accepted.endswith(" "):
        accepted = f"{accepted} "
    return AcceptedSuggestion(text=accepted, cursor_position=len(accepted))


def run_tui() -> None:
    node = shutil.which("node")
    if not node:
        raise ImportError("Node.js is required for `sadquant tui`, but `node` was not found on PATH.")

    script = _ink_entrypoint()
    if not script.exists():
        raise ImportError(
            "The Ink TUI has not been built. Run `npm install` and `npm run build` from `ink_tui/`, then retry `sadquant tui`."
        )

    env = os.environ.copy()
    env["SADQUANT_TUI_PYTHON"] = sys.executable
    env["SADQUANT_TUI_PROJECT"] = str(Path.cwd())
    env["SADQUANT_TUI_VERSION"] = _package_version()
    env["SADQUANT_TUI_BRIDGE_MODULE"] = "sadquant.tui_bridge"
    env["SADQUANT_TUI_CLI_MODULE"] = "sadquant.cli"
    env["PYTHONPATH"] = _pythonpath(env)
    env["FORCE_COLOR"] = "1"
    env.pop("NO_COLOR", None)

    result = subprocess.run([node, str(script)], env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def _ink_entrypoint() -> Path:
    return Path(__file__).resolve().parents[2] / "ink_tui" / "dist" / "cli.js"


def _pythonpath(env: dict[str, str]) -> str:
    paths = [path for path in sys.path if path]
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return os.pathsep.join(dict.fromkeys(paths))


def _package_version() -> str:
    try:
        return f"v{version('sadquant')}"
    except PackageNotFoundError:
        return "dev"


def _current_token(text: str) -> str:
    if not text or text.endswith(" "):
        return ""
    return text.split()[-1]
