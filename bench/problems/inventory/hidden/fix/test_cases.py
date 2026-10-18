from stock.report import stock_report


def test_case_of_washers():
    assert stock_report(["B200,1,case"]) == "B200 墊圈: 24\nTOTAL units 24"


def test_mixed_units_of_one_item():
    assert stock_report(["C300,1,case", "C300,2,pack", "C300,3,unit"]) == "C300 螺帽: 63\nTOTAL units 63"


def test_cases_of_several_items():
    assert stock_report(["A100,3,case", "B200,2,case"]) == "A100 螺絲: 300\nB200 墊圈: 48\nTOTAL units 348"
