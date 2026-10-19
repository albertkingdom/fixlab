from stock.report import stock_report


def test_packs():
    assert stock_report(["A100,2,pack"]) == "A100 螺絲: 20\nTOTAL units 20"


def test_unknown_item_is_skipped():
    assert stock_report(["Z999,5,unit", "A100,1,unit"]) == "A100 螺絲: 1\nTOTAL units 1"


def test_empty_receipt():
    assert stock_report([]) == "TOTAL units 0"
