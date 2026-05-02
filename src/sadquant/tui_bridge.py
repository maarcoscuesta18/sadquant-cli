from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any

from sadquant.tui import accept_suggestion
from sadquant.tui_commands import CommandAction, CommandSuggestion, SlashCommand, TuiCommandController, command_schema, compose_slash_command, suggestions_for


class TuiBridge:
    def __init__(self) -> None:
        self.controller = TuiCommandController()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = str(request.get("type", ""))
        if kind == "hello":
            return self._response({"state": self._state()})
        if kind == "state":
            return self._response({"state": self._state()})
        if kind == "submit":
            action = self.controller.submit(str(request.get("text", "")))
            return self._response({"action": _action(action), "state": self._state()})
        if kind == "suggestions":
            text = str(request.get("text", ""))
            suggestions = [_suggestion(item) for item in self.controller.suggestions(text)]
            return self._response({"suggestions": suggestions, "state": self._state()})
        if kind == "accept_suggestion":
            text = str(request.get("text", ""))
            suggestion = _command_suggestion_from_request(request.get("suggestion"))
            accepted = accept_suggestion(text, suggestion)
            return self._response({"accepted": asdict(accepted), "state": self._state()})
        if kind == "command_schema":
            command = str(request.get("command", self.controller.active_command or ""))
            return self._response({"schema": command_schema(command), "state": self._state()})
        if kind == "compose_command":
            command = str(request.get("command", self.controller.active_command or ""))
            raw_args = request.get("args", [])
            if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
                raise ValueError("compose_command requires string args.")
            composed = compose_slash_command(command, raw_args)
            return self._response({"command": _command(composed), "input": composed.display, "state": self._state()})
        if kind == "option_suggestions":
            command = request.get("command", self.controller.active_command)
            text = str(request.get("text", ""))
            suggestions = suggestions_for(text, active_command=str(command) if command else None)
            return self._response({"suggestions": [_suggestion(item) for item in suggestions], "state": self._state()})
        return self._response({"error": f"Unknown bridge request type '{kind}'."}, ok=False)

    def _state(self) -> dict[str, Any]:
        planned = self.controller.planned_command
        return {
            "modeLabel": self.controller.mode_label,
            "planMode": self.controller.plan_mode,
            "activeCommand": self.controller.active_command,
            "activePrompt": self.controller.active_prompt,
            "plannedCommand": _command(planned) if planned else None,
        }

    @staticmethod
    def _response(payload: dict[str, Any], ok: bool = True) -> dict[str, Any]:
        return {"ok": ok, **payload}


def run_bridge() -> None:
    bridge = TuiBridge()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = bridge.handle(request)
        except Exception as exc:  # noqa: BLE001 - bridge must report all failures as JSON.
            response = {"ok": False, "error": str(exc)}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _action(action: CommandAction) -> dict[str, Any]:
    return {
        "kind": action.kind,
        "message": action.message,
        "command": _command(action.command) if action.command else None,
    }


def _command(command: SlashCommand | None) -> dict[str, Any] | None:
    if command is None:
        return None
    return {
        "name": command.name,
        "args": command.args,
        "argv": command.argv,
        "raw": command.raw,
        "native": command.native,
        "display": command.display,
    }


def _suggestion(suggestion: CommandSuggestion) -> dict[str, Any]:
    return {
        "value": suggestion.value,
        "label": suggestion.label,
        "description": suggestion.description,
        "replaceToken": suggestion.replace_token,
    }


def _command_suggestion_from_request(value: Any) -> CommandSuggestion:
    if not isinstance(value, dict):
        raise ValueError("accept_suggestion requires a suggestion object.")
    return CommandSuggestion(
        value=str(value.get("value", "")),
        label=str(value.get("label", "")),
        description=str(value.get("description", "")),
        replace_token=bool(value.get("replaceToken", True)),
    )


if __name__ == "__main__":
    run_bridge()
