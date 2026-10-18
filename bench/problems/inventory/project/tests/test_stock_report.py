from stock.report import stock_report


def test_units_only():
    assert stock_report(["A100,5,unit", "B200,2,unit"]) == "A100 螺絲: 5\nB200 墊圈: 2\nTOTAL units 7"


def test_one_case_of_screws():
    assert stock_report(["A100,2,case"]) == "A100 螺絲: 200\nTOTAL units 200"
