from subs.report import status_report


def test_far_from_expiry_in_both_directions():
    subs = [("alice", "2027-01-01 00:00"), ("bob", "2025-01-01 00:00")]
    assert status_report(subs, "2026-02-28 12:00") == "alice: active until 2027-01-01 00:00\nbob: expired"


def test_a_few_hours_before_expiry():
    # 到期是本地 2026-03-01 00:00，也就是 UTC 2026-02-28 16:00；現在 UTC 12:00，還有 4 小時
    assert status_report([("alice", "2026-03-01 00:00")], "2026-02-28 12:00") == "alice: active until 2026-03-01 00:00"
