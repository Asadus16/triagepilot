"""Drafts a reply once the rule engine has already decided urgency, topic and route.
The model narrates the engine's decision; it does not make it. A narration guardrail
rejects a draft that invents an urgency or topic word the engine didn't produce.
"""

from __future__ import annotations

import json

from app.config import get_settings
from app.llm import gemini
from app.models import Decision, Ticket

_SCHEMA = {"type": "OBJECT", "properties": {"draft_reply": {"type": "STRING"}}, "required": ["draft_reply"]}

_PROMPT = """You write a short, polite reply for a staff member at {business_name}, {business_type},
to edit before sending. Never invent facts the customer didn't state. Never promise a
specific time or outcome the staff member hasn't confirmed.

Customer message: {message}
This ticket's topic: {topic}
"""


def draft_reply(ticket: Ticket, topic: str) -> str:
    s = get_settings()
    prompt = _PROMPT.format(business_name=s.business_name, business_type=s.business_type, message=ticket.message, topic=topic)
    try:
        raw = gemini.generate_structured(prompt, _SCHEMA)
        return json.loads(raw)["draft_reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return "Thank you for reaching out. A team member will follow up shortly."


_FORBIDDEN_IF_ABSENT = {
    # If the engine didn't flag these, the draft should not claim them either.
    "mentions_emergency": ["emergency", "dispatch", "right away"],
    "mentions_legal": ["lawyer", "attorney", "lawsuit"],
}


def guard_draft(draft: str, decision: Decision) -> str:
    """A narration guardrail: if the draft uses language implying a rule that never
    fired, fall back to a neutral draft instead of shipping an inconsistent reply."""
    flagged = {r.rule_id for r in decision.rule_results if r.status.value == "flag"}
    text = draft.lower()
    if not (flagged & {"E01", "E02"}) and any(w in text for w in _FORBIDDEN_IF_ABSENT["mentions_emergency"]):
        return "Thank you for reaching out. A team member will review this and follow up shortly."
    if not (flagged & {"L01", "L02"}) and any(w in text for w in _FORBIDDEN_IF_ABSENT["mentions_legal"]):
        return "Thank you for reaching out. A team member will review this and follow up shortly."
    return draft
