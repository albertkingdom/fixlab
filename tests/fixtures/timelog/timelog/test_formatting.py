from timelog.formatting import format_duration


def test_hours_and_minutes():
    assert format_duration(90) == "1h30m"


def test_whole_hours():
    assert format_duration(120) == "2h"


def test_minutes_only():
    assert format_duration(45) == "45m"
    assert format_duration(0) == "0m"
