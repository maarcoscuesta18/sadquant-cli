from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sadquant.models import RagChunk, RagDocument, RetrievalHit


DEFAULT_VECTOR_DIMS = 256


def default_db_path() -> Path:
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir("sadquant", "sadquant")) / "rag.sqlite"
    except ModuleNotFoundError:
        base = Path(os.getenv("APPDATA", Path.home() / ".local" / "share"))
        return base / "sadquant" / "rag.sqlite"


class RagStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or default_db_path()
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
                CREATE VIRTUAL TABLE IF NOT EXISTS documents
                USING fts5(ticker, source, title, body, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    labels_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    content_hash TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_chunks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    contextual_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    labels_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    vector_json TEXT NOT NULL,
                    source_id TEXT NOT NULL UNIQUE,
                    FOREIGN KEY(doc_id) REFERENCES rag_documents(id)
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts
                USING fts5(ticker, source, title, contextual_text, raw_text, content='rag_chunks', content_rowid='id')
                """
            )

    def add(
        self,
        doc: RagDocument,
        *,
        labels: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        contextualize: bool = True,
    ) -> int:
        labels = _default_labels(doc, labels)
        metadata = metadata or {}
        content_hash = _content_hash(doc.ticker, doc.source, doc.title, doc.body)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents(ticker, source, title, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (doc.ticker.upper(), doc.source, doc.title, doc.body, doc.created_at),
            )
            existing = conn.execute(
                "SELECT id FROM rag_documents WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            if existing:
                return int(existing["id"])
            cursor = conn.execute(
                """
                INSERT INTO rag_documents(ticker, source, title, body, created_at, labels_json, metadata_json, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.ticker.upper(),
                    doc.source,
                    doc.title,
                    doc.body,
                    doc.created_at,
                    json.dumps(labels, sort_keys=True),
                    json.dumps(metadata, sort_keys=True, default=str),
                    content_hash,
                ),
            )
            doc_id = int(cursor.lastrowid)
            for index, chunk_body in enumerate(chunk_text(doc.body)):
                context = build_contextual_prefix(doc, labels, chunk_body) if contextualize else ""
                contextual_text = f"{context}\n{chunk_body}".strip()
                source_id = f"{doc.ticker.upper()}:{doc.source}:{doc_id}:{index + 1}"
                vector = embed_text(contextual_text)
                conn.execute(
                    """
                    INSERT INTO rag_chunks(
                        doc_id, ticker, source, title, raw_text, contextual_text, created_at,
                        labels_json, metadata_json, vector_json, source_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        doc.ticker.upper(),
                        doc.source,
                        doc.title,
                        chunk_body,
                        contextual_text,
                        doc.created_at,
                        json.dumps(labels, sort_keys=True),
                        json.dumps(metadata, sort_keys=True, default=str),
                        json.dumps(vector),
                        source_id,
                    ),
                )
            self._rebuild_chunk_fts(conn)
            return doc_id

    def search(self, ticker: str, query: str, limit: int = 5) -> list[RagDocument]:
        ticker = ticker.upper()
        expression = _fts_expression(ticker, query)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ticker, source, title, body, created_at
                FROM documents
                WHERE documents MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (expression, limit),
            ).fetchall()

        return [
            RagDocument(ticker=row["ticker"], source=row["source"], title=row["title"], body=row["body"], created_at=row["created_at"])
            for row in rows
        ]

    def hybrid_search(
        self,
        ticker: str,
        query: str,
        *,
        horizon: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        limit: int = 8,
        candidate_limit: int = 30,
    ) -> list[RetrievalHit]:
        ticker = ticker.upper()
        label_filters = dict(labels or {})
        if horizon:
            label_filters["horizon"] = horizon

        bm25_ranks = self._bm25_ranks(ticker, query, label_filters, candidate_limit)
        vector_ranks = self._vector_ranks(ticker, query, label_filters, candidate_limit)
        fused: dict[int, float] = defaultdict(float)
        for rank, chunk_id in enumerate(bm25_ranks, start=1):
            fused[chunk_id] += 1.0 / (60 + rank)
        for rank, chunk_id in enumerate(vector_ranks, start=1):
            fused[chunk_id] += 1.0 / (60 + rank)

        ordered_ids = [chunk_id for chunk_id, _ in sorted(fused.items(), key=lambda item: item[1], reverse=True)[:limit]]
        if not ordered_ids:
            ordered_ids = self._fallback_ranks(ticker, label_filters, limit)
            for rank, chunk_id in enumerate(ordered_ids, start=1):
                fused[chunk_id] = 1.0 / (120 + rank)
        if not ordered_ids:
            return []

        chunks = self._chunks_by_id(ordered_ids)
        query_vector = embed_text(query)
        hits = []
        for chunk_id in ordered_ids:
            chunk = chunks[chunk_id]
            bm25_score = 1.0 / (1 + bm25_ranks.index(chunk_id)) if chunk_id in bm25_ranks else 0.0
            vector = json.loads(str(chunk.metadata.get("_vector_json", "[]")))
            vector_score = cosine_similarity(query_vector, vector)
            method = "hybrid" if bm25_score and vector_score else "bm25" if bm25_score else "vector"
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    method=method,
                    bm25_score=round(bm25_score, 6),
                    vector_score=round(vector_score, 6),
                    fused_score=round(fused[chunk_id], 6),
                    source_id=chunk.source_id if hasattr(chunk, "source_id") else chunk.metadata.get("source_id", str(chunk_id)),
                )
            )
        return hits

    def _bm25_ranks(self, ticker: str, query: str, labels: dict[str, str], limit: int) -> list[int]:
        expression = _fts_expression(ticker, query)
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT rag_chunks.id, rag_chunks.labels_json
                    FROM rag_chunks_fts
                    JOIN rag_chunks ON rag_chunks_fts.rowid = rag_chunks.id
                    WHERE rag_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (expression, max(limit * 3, limit)),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        return [int(row["id"]) for row in rows if _labels_match(json.loads(row["labels_json"]), labels)][:limit]

    def _vector_ranks(self, ticker: str, query: str, labels: dict[str, str], limit: int) -> list[int]:
        query_vector = embed_text(query)
        scores = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, labels_json, vector_json FROM rag_chunks WHERE ticker = ?",
                (ticker,),
            ).fetchall()
        for row in rows:
            if not _labels_match(json.loads(row["labels_json"]), labels):
                continue
            score = cosine_similarity(query_vector, json.loads(row["vector_json"]))
            if score > 0:
                scores.append((int(row["id"]), score))
        return [chunk_id for chunk_id, _ in sorted(scores, key=lambda item: item[1], reverse=True)[:limit]]

    def _fallback_ranks(self, ticker: str, labels: dict[str, str], limit: int) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, labels_json
                FROM rag_chunks
                WHERE ticker = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (ticker, max(limit * 3, limit)),
            ).fetchall()
        return [int(row["id"]) for row in rows if _labels_match(json.loads(row["labels_json"]), labels)][:limit]

    def _chunks_by_id(self, chunk_ids: list[int]) -> dict[int, RagChunk]:
        placeholders = ",".join("?" for _ in chunk_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, doc_id, ticker, source, title, raw_text, contextual_text, created_at,
                       labels_json, metadata_json, vector_json, source_id
                FROM rag_chunks
                WHERE id IN ({placeholders})
                """,
                chunk_ids,
            ).fetchall()
        chunks = {}
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            metadata["_vector_json"] = row["vector_json"]
            metadata["source_id"] = row["source_id"]
            chunks[int(row["id"])] = RagChunk(
                id=int(row["id"]),
                doc_id=int(row["doc_id"]),
                ticker=row["ticker"],
                source=row["source"],
                title=row["title"],
                raw_text=row["raw_text"],
                contextual_text=row["contextual_text"],
                created_at=row["created_at"],
                labels=json.loads(row["labels_json"]),
                metadata=metadata,
                source_id=row["source_id"],
            )
        return chunks

    def _rebuild_chunk_fts(self, conn: sqlite3.Connection) -> None:
        conn.execute("INSERT INTO rag_chunks_fts(rag_chunks_fts) VALUES('rebuild')")


def chunk_text(text: str, *, max_chars: int = 1800, overlap: int = 200) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + max_chars)
        if end < len(clean):
            boundary = clean.rfind(". ", start, end)
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunks.append(clean[start:end].strip())
        if end >= len(clean):
            break
        start = max(0, end - overlap)
    return chunks


def build_contextual_prefix(doc: RagDocument, labels: dict[str, str], chunk: str) -> str:
    date = _date_label(doc.created_at)
    horizon = labels.get("horizon", "all")
    doc_type = labels.get("doc_type", _doc_type_from_source(doc.source))
    event_type = labels.get("event_type", "general")
    terms = ", ".join(_top_terms(chunk, limit=6))
    return (
        f"Ticker {doc.ticker.upper()} document context: source={doc.source}; title={doc.title}; "
        f"date={date}; horizon={horizon}; document_type={doc_type}; event_type={event_type}; "
        f"key_terms={terms}."
    )


def embed_text(text: str, dims: int = DEFAULT_VECTOR_DIMS) -> list[float]:
    vector = [0.0] * dims
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
        bucket = int.from_bytes(digest, "big") % dims
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 8) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def _fts_expression(ticker: str, query: str) -> str:
    ticker_token = f'"{ticker}"'
    query_tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9_]+", query)
        if token.upper() != ticker.upper()
    ]
    if not query_tokens:
        return ticker_token
    query_expression = " OR ".join(f'"{token}"' for token in query_tokens)
    return f"{ticker_token} AND ({query_expression})"


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", text)]


def _top_terms(text: str, limit: int) -> list[str]:
    stop = {"the", "and", "for", "with", "from", "that", "this", "company", "stock"}
    counts = Counter(token for token in _tokens(text) if token not in stop)
    return [token for token, _ in counts.most_common(limit)]


def _content_hash(ticker: str, source: str, title: str, body: str) -> str:
    payload = "\n".join([ticker.upper(), source, title, body])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _default_labels(doc: RagDocument, labels: Optional[dict[str, str]]) -> dict[str, str]:
    merged = {
        "source_type": doc.source.split(":", 1)[0],
        "doc_type": _doc_type_from_source(doc.source),
        "event_type": "general",
        "horizon": "all",
        "freshness": freshness_bucket(doc.created_at),
    }
    merged.update(labels or {})
    return merged


def _doc_type_from_source(source: str) -> str:
    lower = source.lower()
    if "transcript" in lower:
        return "transcript"
    if "press" in lower:
        return "press_release"
    if "news" in lower:
        return "news"
    if "filing" in lower or "sec" in lower:
        return "filing"
    return "note"


def freshness_bucket(created_at: str, now: Optional[datetime] = None) -> str:
    try:
        value = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    age_days = (now - value).total_seconds() / 86400
    if age_days <= 2:
        return "fresh"
    if age_days <= 30:
        return "recent"
    if age_days <= 180:
        return "stale"
    return "old"


def _date_label(created_at: str) -> str:
    return created_at[:10] if created_at else "unknown"


def _labels_match(row_labels: dict[str, str], filters: dict[str, str]) -> bool:
    for key, value in filters.items():
        if not value:
            continue
        if key == "horizon" and row_labels.get(key) == "all":
            continue
        if row_labels.get(key) != value:
            return False
    return True
