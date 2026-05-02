from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sadquant.rag import default_db_path


def default_journal_path() -> Path:
    return default_db_path().with_name("signals.sqlite")


class SignalJournal:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(os.getenv("SADQUANT_SIGNAL_JOURNAL", default_journal_path()))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    bias TEXT NOT NULL,
                    score REAL NOT NULL,
                    confidence TEXT NOT NULL,
                    question TEXT NOT NULL,
                    cited_evidence_json TEXT NOT NULL,
                    entry_price REAL,
                    invalidation TEXT,
                    target TEXT,
                    review_date TEXT,
                    outcome_label TEXT,
                    outcome_notes TEXT
                )
                """
            )
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(signals)").fetchall()}
            for name, ddl in {
                "entry_price": "ALTER TABLE signals ADD COLUMN entry_price REAL",
                "invalidation": "ALTER TABLE signals ADD COLUMN invalidation TEXT",
                "target": "ALTER TABLE signals ADD COLUMN target TEXT",
                "review_date": "ALTER TABLE signals ADD COLUMN review_date TEXT",
            }.items():
                if name not in existing:
                    conn.execute(ddl)

    def add(
        self,
        *,
        ticker: str,
        horizon: str,
        bias: str,
        score: float,
        confidence: str,
        question: str,
        cited_evidence: list[dict[str, Any]],
        entry_price: float | None = None,
        invalidation: str = "",
        target: str = "",
        review_date: str = "",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO signals(
                    created_at, ticker, horizon, bias, score, confidence, question, cited_evidence_json,
                    entry_price, invalidation, target, review_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    ticker.upper(),
                    horizon,
                    bias,
                    score,
                    confidence,
                    question,
                    json.dumps(cited_evidence, sort_keys=True, default=str),
                    entry_price,
                    invalidation,
                    target,
                    review_date,
                ),
            )
            return int(cursor.lastrowid)

    def get_rows(self, *, horizon: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
        return self.list(horizon=horizon, limit=limit)

    def list(self, *, horizon: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
        sql = "SELECT * FROM signals"
        params: list[Any] = []
        if horizon:
            sql += " WHERE horizon = ?"
            params.append(horizon)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def label_outcome(self, signal_id: int, *, label: str, notes: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE signals SET outcome_label = ?, outcome_notes = ? WHERE id = ?",
                (label, notes, signal_id),
            )
