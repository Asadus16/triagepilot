"""Core types. The LLM only ever produces an ExtractedSignals object (facts, not a
decision). Everything in Decision is computed by the rule engine in app/rules/engine.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Route(str, Enum):
    AUTO_DRAFT = "auto_draft"  # low risk, draft held for a quick approval
    ESCALATE = "escalate"  # safety / emergency language, needs eyes now
    BILLING_REVIEW = "billing_review"  # money at stake, a person checks the numbers
    MANAGER_REVIEW = "manager_review"  # legal risk, repeat contact, or low confidence


class Status(str, Enum):
    PASS = "pass"
    FLAG = "flag"


class Ticket(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    customer_email: EmailStr
    subject: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=8000)


class ExtractedSignals(BaseModel):
    """What the model is allowed to say. Booleans and a confidence score, nothing that
    decides urgency or routing — that is the rule engine's job, never the model's."""

    sentiment: str = "neutral"  # neutral | frustrated | angry
    mentions_emergency: bool = False
    mentions_money: bool = False
    mentions_legal: bool = False
    mentions_cancellation: bool = False
    topic_guess: str = "general"
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RuleResult(BaseModel):
    rule_id: str
    category: str
    status: Status
    message: str
    reason_code: str = ""


class Decision(BaseModel):
    ticket_id: str
    urgency: Urgency
    topic: str
    route: Route
    draft_reply: str
    confidence: float
    reason_codes: list[str]
    rule_results: list[RuleResult]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanReview(BaseModel):
    ticket_id: str
    action: str  # approved | edited | rejected
    note: str = ""
