from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_LOADED = False


def load_dotenv(path: Optional[Path] = None) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding shell env."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    env_path = path or Path.cwd() / ".env"
    if not env_path.exists():
        return

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = _clean_key(key.strip())
        if not key or key in os.environ:
            continue
        os.environ[key] = _clean_value(value.strip())


def _clean_key(key: str) -> str:
    if key.startswith("$env:"):
        return key[5:]
    if key.startswith("export "):
        return key[7:].strip()
    return key


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
