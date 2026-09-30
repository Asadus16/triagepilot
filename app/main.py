"""FastAPI service. n8n calls this to triage a ticket, then routes by the returned
`route` into one of four human review lanes — the same "n8n orchestrates, FastAPI
holds the logic" split as claim-triage-agent and analytics-agent, for the reason
stated in each of their READMEs: n8n Cloud's Code node can't import a library or make
a network call, so real logic has to live somewhere that can.
"""

from __future__ import annotations

from typing import Optional
import uuid

from fastapi import FastAPI, Header, HTTPException

from app.config import get_settings
from app.llm.draft import draft_reply, guard_draft
from app.llm.extract import extract_signals
from app.models import Decision, HumanReview, Ticket
from app.rules.catalog import CATALOG
from app.rules.engine import decide_route, decide_urgency, run_rules
from app.store import get_decision, had_recent_contact, save_decision, save_human_review, save_ticket

app = FastAPI(title="TriagePilot")


def _check_key(x_service_key: str | None) -> None:
    if x_service_key != get_settings().service_api_key:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/rules")
def list_rules():
    """Returns the whole rule catalog, so a client can review it. Same transparency
    principle as claim-triage-agent's GET /rules."""
    return [{"rule_id": r.rule_id, "category": r.category, "description": r.description, "reason_code": r.reason_code} for r in CATALOG]


@app.post("/triage")
def triage(ticket: Ticket, x_service_key: Optional[str] = Header(default=None)) -> Decision:
    _check_key(x_service_key)

    ticket_id = str(uuid.uuid4())
    repeat = had_recent_contact(ticket.customer_email)
    save_ticket(ticket_id, ticket)

    signals = extract_signals(ticket)
    rule_results = run_rules(ticket, signals, repeat)
    flagged = {r.rule_id for r in rule_results if r.status.value == "flag"}

    route = decide_route(flagged)
    urgency = decide_urgency(flagged)
    settings = get_settings()
    topic = signals.topic_guess if signals.topic_guess in {c.strip() for c in settings.categories.split(",")} else "other"

    draft = draft_reply(ticket, topic)

    decision = Decision(
        ticket_id=ticket_id,
        urgency=urgency,
        topic=topic,
        route=route,
        draft_reply=draft,
        confidence=signals.extraction_confidence,
        reason_codes=sorted(flagged),
        rule_results=rule_results,
    )
    decision.draft_reply = guard_draft(draft, decision)
    save_decision(decision)
    return decision


@app.post("/human/{ticket_id}")
def human_review(ticket_id: str, review: HumanReview, x_service_key: Optional[str] = Header(default=None)) -> dict:
    if review.ticket_id != ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id mismatch")
    _check_key(x_service_key)
    if get_decision(ticket_id) is None:
        raise HTTPException(status_code=404, detail="no decision for that ticket_id")
    save_human_review(review)
    return {"ticket_id": ticket_id, "status": get_decision(ticket_id)["status"]}


@app.get("/golden/run")
def golden_run(x_service_key: Optional[str] = Header(default=None)) -> dict:
    _check_key(x_service_key)
    from app.golden import run_golden

    return run_golden()
