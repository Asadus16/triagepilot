"""SQLite audit store. Every ticket, its decision, and every human review is kept, so
any decision is reconstructable by ticket_id — the same audit principle claim-triage-agent
uses for insurance decisions, applied here to support tickets.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings
from app.models import Decision, HumanReview, Ticket

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    ticket_id TEXT PRIMARY KEY REFERENCES tickets(ticket_id),
    urgency TEXT NOT NULL,
    topic TEXT NOT NULL,
    route TEXT NOT NULL,
    draft_reply TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason_codes TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending approval',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rule_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    rule_id TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    reason_code TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    path = Path(get_settings().tickets_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_ticket(ticket_id: str, ticket: Ticket) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tickets VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, ticket.customer_name, ticket.customer_email, ticket.subject, ticket.message, datetime.now(timezone.utc).isoformat()),
        )


def save_decision(decision: Decision) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO decisions (ticket_id, urgency, topic, route, draft_reply, confidence, reason_codes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                decision.ticket_id,
                decision.urgency.value,
                decision.topic,
                decision.route.value,
                decision.draft_reply,
                decision.confidence,
                ",".join(decision.reason_codes),
                decision.created_at,
            ),
        )
        for r in decision.rule_results:
            conn.execute(
                "INSERT INTO rule_results (ticket_id, rule_id, category, status, message, reason_code) VALUES (?, ?, ?, ?, ?, ?)",
                (decision.ticket_id, r.rule_id, r.category, r.status.value, r.message, r.reason_code),
            )


def had_recent_contact(email: str, within_hours: int = 48) -> bool:
    """Real repeat contact check, used by rule R01. A second real ticket in the window
    counts; the one just being decided has not been saved yet when this runs."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE customer_email = ? AND received_at >= ?", (email, cutoff)
        ).fetchone()
        return row["n"] > 0


def save_human_review(review: HumanReview) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO human_reviews (ticket_id, action, note, reviewed_at) VALUES (?, ?, ?, ?)",
            (review.ticket_id, review.action, review.note, datetime.now(timezone.utc).isoformat()),
        )
        if review.action == "approved":
            conn.execute("UPDATE decisions SET status = 'ready to send' WHERE ticket_id = ?", (review.ticket_id,))
        elif review.action == "rejected":
            conn.execute("UPDATE decisions SET status = 'rejected' WHERE ticket_id = ?", (review.ticket_id,))


def get_decision(ticket_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE ticket_id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None
