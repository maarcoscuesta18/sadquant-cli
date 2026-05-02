from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sadquant.models import Thesis, Watchlist
from sadquant.rag import default_db_path


def default_investor_state_path() -> Path:
    return default_db_path().with_name("investor.sqlite")


class InvestorState:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or default_investor_state_path()
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
                CREATE TABLE IF NOT EXISTS watchlist_items(
                    name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(name, ticker)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS theses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    risks TEXT NOT NULL,
                    review_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add_watchlist_tickers(self, name: str, tickers: list[str]) -> Watchlist:
        normalized_name = _normalize_name(name)
        now = _now()
        with self._connect() as conn:
            for ticker in _normalize_tickers(tickers):
                conn.execute(
                    """
                    INSERT INTO watchlist_items(name, ticker, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(name, ticker) DO UPDATE SET updated_at = excluded.updated_at
                    """,
                    (normalized_name, ticker, now, now),
                )
        return self.get_watchlist(normalized_name)

    def remove_watchlist_tickers(self, name: str, tickers: list[str]) -> Watchlist:
        normalized_name = _normalize_name(name)
        with self._connect() as conn:
            conn.executemany(
                "DELETE FROM watchlist_items WHERE name = ? AND ticker = ?",
                [(normalized_name, ticker) for ticker in _normalize_tickers(tickers)],
            )
        return self.get_watchlist(normalized_name)

    def list_watchlists(self) -> list[Watchlist]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, ticker, updated_at
                FROM watchlist_items
                ORDER BY name, ticker
                """
            ).fetchall()
        grouped: dict[str, list[str]] = {}
        updated: dict[str, str] = {}
        for row in rows:
            grouped.setdefault(str(row["name"]), []).append(str(row["ticker"]))
            updated[str(row["name"])] = max(updated.get(str(row["name"]), ""), str(row["updated_at"]))
        return [Watchlist(name=name, tickers=tickers, updated_at=updated[name]) for name, tickers in grouped.items()]

    def get_watchlist(self, name: str) -> Watchlist:
        normalized_name = _normalize_name(name)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ticker, updated_at
                FROM watchlist_items
                WHERE name = ?
                ORDER BY ticker
                """,
                (normalized_name,),
            ).fetchall()
        updated_at = max((str(row["updated_at"]) for row in rows), default="")
        return Watchlist(name=normalized_name, tickers=[str(row["ticker"]) for row in rows], updated_at=updated_at)

    def add_thesis(
        self,
        *,
        ticker: str,
        horizon: str,
        thesis: str,
        evidence: str = "",
        risks: str = "",
        review_date: str = "",
        status: str = "active",
    ) -> int:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO theses(ticker, horizon, thesis, evidence, risks, review_date, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ticker.upper().strip(), horizon, thesis, evidence, risks, review_date, status, now, now),
            )
            return int(cursor.lastrowid)

    def list_theses(self, *, ticker: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> list[Thesis]:
        clauses: list[str] = []
        params: list[object] = []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker.upper().strip())
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM theses"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_thesis_from_row(row) for row in rows]


def _normalize_name(name: str) -> str:
    return name.strip().lower() or "default"


def _normalize_tickers(tickers: list[str]) -> list[str]:
    normalized: list[str] = []
    for ticker in tickers:
        value = ticker.upper().strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _thesis_from_row(row: sqlite3.Row) -> Thesis:
    return Thesis(
        id=int(row["id"]),
        ticker=str(row["ticker"]),
        horizon=str(row["horizon"]),
        thesis=str(row["thesis"]),
        evidence=str(row["evidence"]),
        risks=str(row["risks"]),
        review_date=str(row["review_date"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
