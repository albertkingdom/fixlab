from subs.report import status_report


def test_long_expired():
    assert status_report([("a", "2020-01-01 09:30")], "2026-02-28 12:00") == "a: expired"


def test_names_are_sorted():
    subs = [("zoe", "2030-01-01 00:00"), ("amy", "2030-01-01 00:00")]
    assert status_report(subs, "2026-01-01 00:00") == "amy: active until 2030-01-01 00:00\nzoe: active until 2030-01-01 00:00"


def test_no_subscriptions_is_an_empty_report():
    assert status_report([], "2026-01-01 00:00") == ""
