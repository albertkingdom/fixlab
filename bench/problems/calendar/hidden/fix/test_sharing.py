from datetime import date

from cal.events import Event
from cal.report import conflict_report


def test_two_one_day_events_on_the_same_day():
    events = [Event("Lunch", date(2026, 6, 2), date(2026, 6, 2)), Event("Call", date(2026, 6, 2), date(2026, 6, 2))]
    assert conflict_report(events) == "Call <-> Lunch"


def test_last_day_meets_first_day_of_the_next():
    events = [Event("Trip", date(2026, 7, 1), date(2026, 7, 7)), Event("Move", date(2026, 7, 7), date(2026, 7, 9))]
    assert conflict_report(events) == "Move <-> Trip"


def test_chain_of_events_that_touch():
    events = [Event("A", date(2026, 5, 1), date(2026, 5, 2)), Event("B", date(2026, 5, 2), date(2026, 5, 3)),
              Event("C", date(2026, 5, 3), date(2026, 5, 4))]
    assert conflict_report(events) == "A <-> B\nB <-> C"
