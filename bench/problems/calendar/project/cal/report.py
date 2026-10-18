"""行事曆報表。"""

from cal.conflicts import find_conflicts
from cal.duration import days_booked


def conflict_report(events):
    pairs = find_conflicts(events)
    if not pairs:
        return "No conflicts"
    return "\n".join(f"{a} <-> {b}" for a, b in pairs)


def booking_summary(events):
    return "\n".join(f"{event.name}: {days_booked(event)} days" for event in sorted(events, key=lambda e: e.name))
