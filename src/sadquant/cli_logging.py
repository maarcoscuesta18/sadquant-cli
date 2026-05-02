from __future__ import annotations

import logging
import os
import re
from hashlib import sha1
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Sequence


LOG_FILE_ENV = "SADQUANT_LOG_FILE"


def configure_cli_logging(log_dir: Optional[Path] = None, cli_input: Optional[Sequence[str]] = None) -> Path:
    directory = log_dir or _default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / _log_filename(cli_input)

    logger = logging.getLogger("sadquant")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_sadquant_cli_handler", False):
            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler._sadquant_cli_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)

    os.environ[LOG_FILE_ENV] = str(log_file)
    logger.debug("CLI logging initialized at %s", log_file)
    return log_file


def active_log_file() -> Optional[str]:
    return os.getenv(LOG_FILE_ENV)


def _default_log_dir() -> Path:
    return Path.cwd() / "logs"


def _log_filename(cli_input: Optional[Sequence[str]]) -> str:
    if not cli_input:
        return "sadquant-cli.log"

    normalized = " ".join(str(part).strip() for part in cli_input if str(part).strip())
    if not normalized:
        return "sadquant-cli.log"

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    slug = slug[:96].strip("-") or "cli"
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:8]
    return f"sadquant-{slug}-{digest}.log"
