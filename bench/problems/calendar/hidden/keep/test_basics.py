from datetime import date

from cal.events import Event
from cal.report import booking_summary, conflict_report


def test_a_day_apart_is_not_a_conflict():
    events = [Event("A", date(2026, 5, 1), date(2026, 5, 2)), Event("B", date(2026, 5, 3), date(2026, 5, 4))]
    assert conflict_report(events) == "No conflicts"


def test_an_event_inside_another_conflicts():
    events = [Event("Big", date(2026, 5, 1), date(2026, 5, 10)), Event("Small", date(2026, 5, 4), date(2026, 5, 5))]
    assert conflict_report(events) == "Big <-> Small"


def test_booking_summary_counts_both_ends():
    events = [Event("Trip", date(2026, 7, 1), date(2026, 7, 7)), Event("Lunch", date(2026, 7, 2), date(2026, 7, 2))]
    assert booking_summary(events) == "Lunch: 1 days\nTrip: 7 days"
