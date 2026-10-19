from datetime import date

from cal.events import Event
from cal.report import conflict_report


def test_separate_events_do_not_conflict():
    events = [Event("Standup", date(2026, 6, 1), date(2026, 6, 2)), Event("Review", date(2026, 6, 4), date(2026, 6, 5))]
    assert conflict_report(events) == "No conflicts"


def test_events_sharing_a_day_conflict():
    events = [Event("Standup", date(2026, 6, 1), date(2026, 6, 3)), Event("Review", date(2026, 6, 3), date(2026, 6, 5))]
    assert conflict_report(events) == "Review <-> Standup"
