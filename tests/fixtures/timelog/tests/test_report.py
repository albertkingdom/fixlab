from timelog.report import weekly_total


def test_single_unit_entries():
    assert weekly_total(["2h", "30m"]) == 2.5


def test_mixed_entries():
    total = weekly_total(["1h30m", "45m", "2h"])
    assert total == 4.25, f"{total} != 4.25"
