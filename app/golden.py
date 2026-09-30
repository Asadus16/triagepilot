"""Golden regression runner. Tests the rule engine directly against hand verified
cases (data/golden/cases.json) — a true oracle, not a copy of the code, same
principle as analytics-agent's golden set. This exercises the deterministic path
only (ticket + signals -> route + urgency), since that is the part a code change can
silently break; LLM extraction quality is a separate, softer concern.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import ExtractedSignals, Ticket
from app.rules.engine import decide_route, decide_urgency, run_rules

CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "golden" / "cases.json"


def run_golden() -> dict:
    cases = json.loads(CASES_PATH.read_text())
    results = []
    for case in cases:
        ticket = Ticket(**case["ticket"])
        signals = ExtractedSignals(**case["signals"])
        rule_results = run_rules(ticket, signals, case["repeat_contact"])
        flagged = {r.rule_id for r in rule_results if r.status.value == "flag"}
        route = decide_route(flagged).value
        urgency = decide_urgency(flagged).value
        passed = route == case["expected_route"] and urgency == case["expected_urgency"]
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "route": route,
                "expected_route": case["expected_route"],
                "urgency": urgency,
                "expected_urgency": case["expected_urgency"],
            }
        )
    passed_count = sum(1 for r in results if r["passed"])
    return {"passed": passed_count, "total": len(results), "results": results}
