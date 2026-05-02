from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

OutputFormat = Literal["table", "json", "csv", "markdown"]


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return to_plain_data(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass
    return value


def emit_structured(value: Any, *, output_format: OutputFormat, output: Optional[Path] = None) -> None:
    payload = _format_payload(value, output_format)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        return
    sys.stdout.write(payload)
    if not payload.endswith("\n"):
        sys.stdout.write("\n")


def _format_payload(value: Any, output_format: OutputFormat) -> str:
    data = to_plain_data(value)
    if output_format == "json":
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if output_format == "csv":
        return rows_to_csv(_coerce_rows(data))
    if output_format == "markdown":
        return _markdown(data)
    raise ValueError("table output is rendered by the command.")


def rows_to_csv(rows: Iterable[dict[str, Any]]) -> str:
    materialized = list(rows)
    if not materialized:
        return ""
    columns: list[str] = []
    for row in materialized:
        for key in row:
            if key not in columns:
                columns.append(key)
    from io import StringIO

    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows([{key: _csv_value(value) for key, value in row.items()} for row in materialized])
    return handle.getvalue()


def _coerce_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row if isinstance(row, dict) else {"value": row} for row in data]
    if isinstance(data, dict):
        for key in ("rows", "results", "tickers", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [row if isinstance(row, dict) else {"value": row} for row in value]
        return [data]
    return [{"value": data}]


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(to_plain_data(value), sort_keys=True, ensure_ascii=False)
    return value


def _markdown(data: Any) -> str:
    if isinstance(data, list):
        return "\n".join(_markdown(item) for item in data)
    if isinstance(data, dict):
        lines = []
        title = data.get("ticker") or data.get("name") or data.get("recipe")
        if title:
            lines.append(f"## {title}")
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"- **{key}:** `{json.dumps(to_plain_data(value), sort_keys=True, ensure_ascii=False)}`")
            else:
                lines.append(f"- **{key}:** {value}")
        return "\n".join(lines)
    return str(data)
