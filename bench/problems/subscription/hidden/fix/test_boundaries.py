from subs.report import status_report


def test_one_minute_before_expiry_is_active():
    assert status_report([("a", "2026-03-01 00:00")], "2026-02-28 15:59") == "a: active until 2026-03-01 00:00"


def test_the_exact_moment_of_expiry_is_expired():
    assert status_report([("a", "2026-03-01 00:00")], "2026-02-28 16:00") == "a: expired"


def test_morning_expiry_seen_late_the_evening_before_in_utc():
    assert status_report([("a", "2026-03-01 08:00")], "2026-02-28 23:59") == "a: active until 2026-03-01 08:00"
