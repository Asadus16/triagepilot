"""The rule catalog: deterministic ticket routing rules a client can read. No LLM, no
randomness. Each rule is a distinct, real check, not padding for a node count — the
engine (engine.py) runs them all and turns every FLAG into a reason code.

Categories:
  E  emergency / safety language      L  legal or regulatory risk
  M  money at stake                   R  repeat, unresolved contact
  C  extraction quality too low to trust     S  escalating tone (deterministic, not the LLM's opinion)
  T  topic outside the configured category list
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.models import ExtractedSignals, Status, Ticket

# A rule returns its status plus a human readable message.
RuleFn = Callable[[Ticket, ExtractedSignals, bool], "tuple[Status, str]"]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    description: str
    reason_code: str  # emitted when the rule FLAGs
    fn: RuleFn


def _ok() -> "tuple[Status, str]":
    return (Status.PASS, "")


def _flag(message: str) -> "tuple[Status, str]":
    return (Status.FLAG, message)


_EMERGENCY_WORDS = re.compile(r"\b(emergency|urgent|right now|asap|flooding|fire|gas leak|can't breathe)\b", re.I)
_LEGAL_WORDS = re.compile(r"\b(lawyer|attorney|lawsuit|sue|bbb|better business bureau|fraud)\b", re.I)
_MONEY_WORDS = re.compile(r"\b(refund|chargeback|dispute the charge|overcharged)\b", re.I)
_DOLLAR_AMOUNT = re.compile(r"\$\s?(\d{2,6})|(\d{2,6})\s?dollars")
_SHOUTING = re.compile(r"[A-Z]{6,}|!{2,}")


def _e01_emergency_keywords(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if _EMERGENCY_WORDS.search(f"{t.subject} {t.message}"):
        return _flag("Message uses explicit emergency language.")
    return _ok()


def _e02_emergency_signal(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if s.mentions_emergency:
        return _flag("Model read this as describing an emergency or safety risk.")
    return _ok()


def _l01_legal_keywords(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if _LEGAL_WORDS.search(f"{t.subject} {t.message}"):
        return _flag("Message mentions legal or regulatory action.")
    return _ok()


def _l02_legal_signal(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if s.mentions_legal:
        return _flag("Model read this as describing legal or regulatory risk.")
    return _ok()


def _m01_money_keywords(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if _MONEY_WORDS.search(f"{t.subject} {t.message}"):
        return _flag("Message asks for a refund or disputes a charge.")
    return _ok()


def _m02_money_signal(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if s.mentions_money and s.topic_guess == "billing":
        return _flag("Model read this as a billing dispute.")
    return _ok()


def _m03_cancellation(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if s.mentions_cancellation:
        return _flag("Customer is asking to cancel, a retention and billing matter.")
    return _ok()


def _m04_dollar_amount(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    match = _DOLLAR_AMOUNT.search(t.message)
    if match:
        amount = int(match.group(1) or match.group(2))
        if amount >= 100:
            return _flag(f"Message names a specific amount (${amount}) worth a second look.")
    return _ok()


def _r01_repeat_contact(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if repeat:
        return _flag("This email has contacted support again within 48 hours.")
    return _ok()


def _c01_low_confidence(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if s.extraction_confidence < 0.4:
        return _flag("Extraction confidence is too low to trust the automatic read.")
    return _ok()


def _c02_too_short(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if len(t.message.strip()) < 15:
        return _flag("Message is too short to classify reliably.")
    return _ok()


def _s01_angry_tone(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if s.sentiment == "angry":
        return _flag("Model read the tone as angry.")
    return _ok()


def _s02_shouting(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    if _SHOUTING.search(t.message):
        return _flag("Message uses all caps or repeated punctuation.")
    return _ok()


def _t01_topic_in_catalog(t: Ticket, s: ExtractedSignals, repeat: bool) -> "tuple[Status, str]":
    from app.config import get_settings

    allowed = {c.strip() for c in get_settings().categories.split(",")}
    if s.topic_guess not in allowed:
        return _flag(f"Model's topic guess '{s.topic_guess}' is outside the configured category list.")
    return _ok()


CATALOG: list[Rule] = [
    Rule("E01", "emergency", "Explicit emergency language in the ticket text", "emergency_keyword", _e01_emergency_keywords),
    Rule("E02", "emergency", "Model read the ticket as describing an emergency", "emergency_signal", _e02_emergency_signal),
    Rule("L01", "legal", "Legal or regulatory keywords in the ticket text", "legal_keyword", _l01_legal_keywords),
    Rule("L02", "legal", "Model read the ticket as describing legal risk", "legal_signal", _l02_legal_signal),
    Rule("M01", "money", "Refund or chargeback language in the ticket text", "money_keyword", _m01_money_keywords),
    Rule("M02", "money", "Model read the ticket as a billing dispute", "money_signal", _m02_money_signal),
    Rule("M03", "money", "Customer is asking to cancel", "cancellation_signal", _m03_cancellation),
    Rule("M04", "money", "A specific dollar amount worth a second look", "dollar_amount", _m04_dollar_amount),
    Rule("R01", "repeat", "Same email contacted support again within 48 hours", "repeat_contact", _r01_repeat_contact),
    Rule("C01", "confidence", "Extraction confidence below the trust threshold", "low_confidence", _c01_low_confidence),
    Rule("C02", "confidence", "Message too short to classify reliably", "too_short", _c02_too_short),
    Rule("S01", "tone", "Model read the tone as angry", "angry_tone", _s01_angry_tone),
    Rule("S02", "tone", "All caps or repeated punctuation in the message", "shouting", _s02_shouting),
    Rule("T01", "topic", "Topic guess outside the configured category list", "topic_out_of_catalog", _t01_topic_in_catalog),
]
