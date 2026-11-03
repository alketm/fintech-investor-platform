"""Local audit trail for chat requests: SQLite store, cost estimates and a small report CLI."""

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from alko_backend.config import AUDIT_DB, AUDIT_RETENTION_DAYS, MODEL_PRICES

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    duration_ms INTEGER,
    agent TEXT NOT NULL,
    view TEXT,
    portfolio_id TEXT,
    question TEXT NOT NULL,
    reply TEXT,
    status TEXT NOT NULL,
    error TEXT,
    guardrail_outcome TEXT,
    guardrail_category TEXT,
    guardrail_source TEXT,
    guardrail_reason TEXT
);
CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES requests(id),
    agent TEXT NOT NULL,
    depth INTEGER NOT NULL,
    turn INTEGER NOT NULL,
    requested_model TEXT NOT NULL,
    served_model TEXT,
    api_request_id TEXT,
    stop_reason TEXT,
    refusal_category TEXT,
    fallback_used INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    est_cost_usd REAL,
    duration_ms INTEGER,
    thinking TEXT
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES requests(id),
    agent TEXT NOT NULL,
    depth INTEGER NOT NULL,
    tool TEXT NOT NULL,
    server TEXT,
    input TEXT,
    result TEXT,
    is_error INTEGER NOT NULL,
    denied INTEGER NOT NULL,
    duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS model_calls_request ON model_calls(request_id);
CREATE INDEX IF NOT EXISTS tool_calls_request ON tool_calls(request_id);
"""

TOKEN_FIELDS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_tokens": "cache_read_input_tokens",
    "cache_write_tokens": "cache_creation_input_tokens",
}


def _tokens(usage: Any) -> dict[str, int]:
    return {name: getattr(usage, attr, 0) or 0 for name, attr in TOKEN_FIELDS.items()}


def _attempts(usage: Any, served_model: str | None) -> list[tuple[str | None, dict[str, int]]]:
    """(model, tokens) per attempt. `usage.iterations` covers every attempt when a fallback ran; the top-level
    usage then covers only the attempt that produced the returned message."""
    iterations = getattr(usage, "iterations", None)
    if iterations:
        return [(getattr(i, "model", None) or served_model, _tokens(i)) for i in iterations]
    return [(served_model, _tokens(usage))]


def estimate_cost(model: str | None, tokens: dict[str, int]) -> float | None:
    """Estimated USD for one attempt, or None when the model has no listed price."""
    prices = MODEL_PRICES.get(model or "")
    if prices is None:
        return None
    input_price, output_price, cache_read_price = prices
    return (
        tokens["input_tokens"] * input_price
        + tokens["output_tokens"] * output_price
        + tokens["cache_read_tokens"] * cache_read_price
        + tokens["cache_write_tokens"] * input_price * 1.25
    ) / 1_000_000


def summarize_usage(usage: Any, served_model: str | None) -> dict[str, Any]:
    """Token totals and estimated cost across all attempts; cost is None if any attempt's model is unpriced."""
    attempts = _attempts(usage, served_model)
    totals = {name: sum(tokens[name] for _, tokens in attempts) for name in TOKEN_FIELDS}
    costs = [estimate_cost(model, tokens) for model, tokens in attempts]
    return {**totals, "est_cost_usd": None if None in costs else sum(costs)}


@dataclass
class RequestAudit:
    """Collects one request's records in memory; `AuditStore.flush` writes them in one transaction."""

    agent: str
    question: str
    view: str | None = None
    portfolio_id: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    reply: str | None = None
    status: str = "error"
    error: str | None = None
    guardrail: dict[str, str | None] = field(default_factory=dict)
    model_calls: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    total_tokens: int = 0
    _started: float = field(default_factory=perf_counter)

    def record_model_call(
        self, agent: str, depth: int, turn: int, requested_model: str, response: Any, duration_ms: int
    ) -> None:
        usage = getattr(response, "usage", None)
        served_model = getattr(response, "model", None)
        summary = summarize_usage(usage, served_model)
        stop_details = getattr(response, "stop_details", None)
        iterations = getattr(usage, "iterations", None) or []
        self.total_tokens += sum(summary[name] for name in TOKEN_FIELDS)
        self.model_calls.append(
            {
                **summary,
                "agent": agent,
                "depth": depth,
                "turn": turn,
                "requested_model": requested_model,
                "served_model": served_model,
                "api_request_id": getattr(response, "_request_id", None),
                "stop_reason": getattr(response, "stop_reason", None),
                "refusal_category": getattr(stop_details, "category", None),
                "fallback_used": any(getattr(i, "type", None) == "fallback_message" for i in iterations),
                "duration_ms": duration_ms,
                "thinking": "\n\n".join(b.thinking for b in response.content if b.type == "thinking"),
            }
        )

    def record_tool_call(
        self,
        agent: str,
        depth: int,
        tool: str,
        server: str | None,
        args: Any,
        result: str,
        is_error: bool,
        denied: bool,
        duration_ms: int,
    ) -> None:
        self.tool_calls.append(
            {
                "agent": agent,
                "depth": depth,
                "tool": tool,
                "server": server,
                "input": json.dumps(args, default=str),
                "result": result,
                "is_error": is_error,
                "denied": denied,
                "duration_ms": duration_ms,
            }
        )

    def finish(self, reply: str | None, status: str, error: str | None = None) -> None:
        self.reply, self.status, self.error = reply, status, error

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "duration_ms": int((perf_counter() - self._started) * 1000),
            "agent": self.agent,
            "view": self.view,
            "portfolio_id": self.portfolio_id,
            "question": self.question,
            "reply": self.reply,
            "status": self.status,
            "error": self.error,
            "guardrail_outcome": self.guardrail.get("outcome"),
            "guardrail_category": self.guardrail.get("category"),
            "guardrail_source": self.guardrail.get("source"),
            "guardrail_reason": self.guardrail.get("reason"),
        }


def _insert(db: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    columns = ", ".join(row)
    values = ", ".join(f":{c}" for c in row)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({values})", row)


class AuditStore:
    def __init__(self, path: Path = AUDIT_DB) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def init(self, retention_days: int = AUDIT_RETENTION_DAYS) -> None:
        """Create the owner-only database if needed and purge expired requests."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        os.close(os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600))
        os.chmod(self.path, 0o600)
        with closing(self._connect()) as db, db:
            db.executescript(SCHEMA)
        self.purge(retention_days)

    def purge(self, retention_days: int = AUDIT_RETENTION_DAYS) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        expired = "SELECT id FROM requests WHERE started_at < ?"
        with closing(self._connect()) as db, db:
            db.execute(f"DELETE FROM model_calls WHERE request_id IN ({expired})", (cutoff,))
            db.execute(f"DELETE FROM tool_calls WHERE request_id IN ({expired})", (cutoff,))
            db.execute("DELETE FROM requests WHERE started_at < ?", (cutoff,))

    def save(self, audit: RequestAudit) -> None:
        with closing(self._connect()) as db, db:
            _insert(db, "requests", audit.to_row())
            for call in audit.model_calls:
                _insert(db, "model_calls", {"request_id": audit.id, **call})
            for call in audit.tool_calls:
                _insert(db, "tool_calls", {"request_id": audit.id, **call})

    async def flush(self, audit: RequestAudit) -> None:
        """Save off the event loop. A failed write is logged and never affects the response."""
        try:
            await asyncio.to_thread(self.save, audit)
        except (sqlite3.Error, OSError):
            logger.exception("Could not write audit record for request %s", audit.id)

    def usage(self, days: int = 30) -> dict[str, list[dict]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        totals = """COUNT(DISTINCT m.request_id) AS requests, SUM(m.input_tokens) AS input_tokens,
            SUM(m.output_tokens) AS output_tokens, SUM(m.cache_read_tokens) AS cache_read_tokens,
            SUM(m.cache_write_tokens) AS cache_write_tokens, SUM(m.est_cost_usd) AS est_cost_usd,
            SUM(m.est_cost_usd IS NULL) AS unpriced_calls"""
        joined = "FROM model_calls m JOIN requests r ON r.id = m.request_id WHERE r.started_at >= ?"
        queries = {
            "by_day": f"SELECT substr(r.started_at, 1, 10) AS day, {totals} {joined} GROUP BY day ORDER BY day",
            "by_agent": f"SELECT m.agent, {totals} {joined} GROUP BY m.agent ORDER BY m.agent",
            "by_model": f"SELECT m.served_model AS model, {totals} {joined} GROUP BY model ORDER BY model",
            "guardrail": """SELECT guardrail_outcome AS outcome, guardrail_source AS source, COUNT(*) AS requests
                FROM requests WHERE started_at >= ? GROUP BY outcome, source ORDER BY outcome, source""",
        }
        with closing(self._connect()) as db:
            return {name: [dict(row) for row in db.execute(sql, (cutoff,))] for name, sql in queries.items()}

    def recent(self, limit: int = 20) -> list[dict]:
        sql = """SELECT r.id, r.started_at, r.agent, r.status, r.guardrail_outcome, r.question,
                COALESCE(SUM(m.input_tokens + m.output_tokens + m.cache_read_tokens + m.cache_write_tokens), 0)
                    AS tokens,
                SUM(m.est_cost_usd) AS est_cost_usd
            FROM requests r LEFT JOIN model_calls m ON m.request_id = r.id
            GROUP BY r.id ORDER BY r.started_at DESC LIMIT ?"""
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute(sql, (limit,))]

    def get(self, request_id: str) -> dict | None:
        with closing(self._connect()) as db:
            request = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
            if request is None:
                return None
            children = {
                table: [
                    dict(row)
                    for row in db.execute(
                        f"SELECT * FROM {table} WHERE request_id = ? ORDER BY id", (request_id,)
                    )
                ]
                for table in ("model_calls", "tool_calls")
            }
        return {**dict(request), **children}


def main(argv: list[str] | None = None, path: Path = AUDIT_DB) -> int:
    parser = argparse.ArgumentParser(prog="python -m alko_backend.audit", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    usage = commands.add_parser("usage", help="tokens and estimated cost by day, agent and model")
    usage.add_argument("--days", type=int, default=30)
    recent = commands.add_parser("list", help="recent requests")
    recent.add_argument("--limit", type=int, default=20)
    show = commands.add_parser("show", help="one request's full record, including thinking summaries")
    show.add_argument("request_id")
    args = parser.parse_args(argv)

    if not Path(path).exists():
        print(f"No audit database at {path}", file=sys.stderr)
        return 1
    store = AuditStore(path)
    if args.command == "usage":
        result: Any = store.usage(args.days)
    elif args.command == "list":
        result = store.recent(args.limit)
    else:
        result = store.get(args.request_id)
        if result is None:
            print(f"No request {args.request_id}", file=sys.stderr)
            return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
