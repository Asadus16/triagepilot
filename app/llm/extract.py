"""Turn a ticket into validated ExtractedSignals. The model only produces booleans, a
sentiment word and a topic guess — it never decides urgency or a route, and it never
drafts a reply here. Extraction failing to parse fails closed (a low confidence
signal, which the rule catalog routes to a human), not a crash.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.config import get_settings
from app.llm import gemini
from app.models import ExtractedSignals, Ticket

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "sentiment": {"type": "STRING", "enum": ["neutral", "frustrated", "angry"]},
        "mentions_emergency": {"type": "BOOLEAN"},
        "mentions_money": {"type": "BOOLEAN"},
        "mentions_legal": {"type": "BOOLEAN"},
        "mentions_cancellation": {"type": "BOOLEAN"},
        "topic_guess": {"type": "STRING"},
        "extraction_confidence": {"type": "NUMBER"},
    },
    "required": ["sentiment", "mentions_emergency", "mentions_money", "mentions_legal", "mentions_cancellation", "topic_guess", "extraction_confidence"],
}

_PROMPT = """You read one customer support ticket for {business_name}, {business_type}.
Categories: {categories}.

Extract facts only. Do not decide urgency or what should happen next, another system
does that. Set extraction_confidence low (under 0.4) if the message is vague, garbled
or you are unsure what it is about.

Subject: {subject}
Message: {message}
"""


def extract_signals(ticket: Ticket) -> ExtractedSignals:
    s = get_settings()
    prompt = _PROMPT.format(
        business_name=s.business_name,
        business_type=s.business_type,
        categories=s.categories,
        subject=ticket.subject,
        message=ticket.message,
    )
    try:
        raw = gemini.generate_structured(prompt, _SCHEMA)
        data = json.loads(raw)
        return ExtractedSignals(**data)
    except (gemini.ReplayMiss,):
        raise
    except (json.JSONDecodeError, ValidationError, KeyError, TypeError):
        # Fail closed: an unparseable read is a low confidence read, not a crash. The
        # rule catalog's C01 rule routes this straight to a human.
        return ExtractedSignals(extraction_confidence=0.0, topic_guess="other")
