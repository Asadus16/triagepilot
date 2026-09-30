"""Deterministic decision engine. Runs the rule catalog and turns the results into a
route and an urgency. The routing is transparent and rule driven; the LLM's only job
elsewhere is to extract signals and draft a reply, never to decide either one.
"""

from __future__ import annotations

from app.models import ExtractedSignals, Route, RuleResult, Status, Ticket, Urgency
from app.rules.catalog import CATALOG

_ESCALATE_RULES = {"E01", "E02"}
_MANAGER_RULES = {"L01", "L02", "R01", "C01", "C02"}
_BILLING_RULES = {"M01", "M02", "M03", "M04"}
_TONE_RULES = {"S01", "S02"}


def run_rules(ticket: Ticket, signals: ExtractedSignals, repeat_contact: bool) -> list[RuleResult]:
    results = []
    for rule in CATALOG:
        status, message = rule.fn(ticket, signals, repeat_contact)
        results.append(
            RuleResult(
                rule_id=rule.rule_id,
                category=rule.category,
                status=status,
                message=message,
                reason_code=rule.reason_code if status == Status.FLAG else "",
            )
        )
    return results


def decide_route(flagged_ids: set[str]) -> Route:
    # Priority order matters: an emergency always wins over a billing question in the
    # same ticket, and a legal or repeat-contact signal always needs a manager before
    # money does, since those carry more downside than a refund question.
    if flagged_ids & _ESCALATE_RULES:
        return Route.ESCALATE
    if flagged_ids & _MANAGER_RULES:
        return Route.MANAGER_REVIEW
    if flagged_ids & _BILLING_RULES:
        return Route.BILLING_REVIEW
    return Route.AUTO_DRAFT


def decide_urgency(flagged_ids: set[str]) -> Urgency:
    if flagged_ids & _ESCALATE_RULES:
        return Urgency.HIGH
    if flagged_ids & (_MANAGER_RULES | _BILLING_RULES) or len(flagged_ids & _TONE_RULES) == 2:
        return Urgency.MEDIUM
    return Urgency.LOW
