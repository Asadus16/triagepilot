from datetime import datetime, timedelta, timezone

from app.models import Route
from app.rules.engine import sla_deadline


def test_escalate_has_the_shortest_deadline():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deadlines = {route: datetime.fromisoformat(sla_deadline(route, now)) for route in Route}
    assert deadlines[Route.ESCALATE] == now + timedelta(minutes=30)
    assert deadlines[Route.ESCALATE] < deadlines[Route.BILLING_REVIEW]
    assert deadlines[Route.ESCALATE] < deadlines[Route.MANAGER_REVIEW]
    assert deadlines[Route.ESCALATE] < deadlines[Route.AUTO_DRAFT]


def test_auto_draft_has_the_longest_deadline():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deadlines = {route: datetime.fromisoformat(sla_deadline(route, now)) for route in Route}
    assert deadlines[Route.AUTO_DRAFT] == max(deadlines.values())
