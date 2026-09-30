from app.models import ExtractedSignals, Ticket
from app.rules.engine import decide_route, decide_urgency, run_rules


def _ticket(**over) -> Ticket:
    base = dict(customer_name="A", customer_email="a@example.com", subject="s", message="a normal question about hours")
    base.update(over)
    return Ticket(**base)


def _signals(**over) -> ExtractedSignals:
    base = dict(sentiment="neutral", mentions_emergency=False, mentions_money=False, mentions_legal=False, mentions_cancellation=False, topic_guess="general", extraction_confidence=0.9)
    base.update(over)
    return ExtractedSignals(**base)


def test_plain_ticket_routes_to_auto_draft_with_low_urgency():
    flagged = {r.rule_id for r in run_rules(_ticket(), _signals(), repeat_contact=False) if r.status.value == "flag"}
    assert decide_route(flagged).value == "auto_draft"
    assert decide_urgency(flagged).value == "low"


def test_emergency_keyword_alone_escalates():
    t = _ticket(message="This is an emergency, water is flooding the store right now.")
    flagged = {r.rule_id for r in run_rules(t, _signals(), repeat_contact=False) if r.status.value == "flag"}
    assert "E01" in flagged
    assert decide_route(flagged).value == "escalate"
    assert decide_urgency(flagged).value == "high"


def test_dollar_amount_under_threshold_does_not_flag():
    t = _ticket(message="I was charged $5 twice, can you check my $5 fee?")
    flagged = {r.rule_id for r in run_rules(t, _signals(), repeat_contact=False) if r.status.value == "flag"}
    assert "M04" not in flagged


def test_repeat_contact_flag_only_fires_when_true():
    signals = _signals()
    t = _ticket()
    flagged_no_repeat = {r.rule_id for r in run_rules(t, signals, repeat_contact=False) if r.status.value == "flag"}
    flagged_repeat = {r.rule_id for r in run_rules(t, signals, repeat_contact=True) if r.status.value == "flag"}
    assert "R01" not in flagged_no_repeat
    assert "R01" in flagged_repeat
    assert decide_route(flagged_repeat).value == "manager_review"


def test_low_confidence_routes_to_manager_review():
    flagged = {r.rule_id for r in run_rules(_ticket(), _signals(extraction_confidence=0.1), repeat_contact=False) if r.status.value == "flag"}
    assert "C01" in flagged
    assert decide_route(flagged).value == "manager_review"


def test_topic_outside_catalog_is_flagged_but_non_blocking():
    flagged = {r.rule_id for r in run_rules(_ticket(), _signals(topic_guess="not_a_real_category"), repeat_contact=False) if r.status.value == "flag"}
    assert "T01" in flagged
    # No other rule fired, so this alone still auto drafts — the flag is recorded, not blocking.
    assert decide_route(flagged).value == "auto_draft"


def test_escalate_outranks_billing_in_the_same_ticket():
    t = _ticket(message="Emergency! Also please refund the $200 I was overcharged.")
    flagged = {r.rule_id for r in run_rules(t, _signals(mentions_emergency=True, mentions_money=True), repeat_contact=False) if r.status.value == "flag"}
    assert decide_route(flagged).value == "escalate"
