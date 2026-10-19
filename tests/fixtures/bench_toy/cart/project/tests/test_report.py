from shop.report import render


def test_small_order():
    assert render([("pen", 2), ("book", 1)]) == "pen x2: 300\nbook x1: 1200\nTOTAL 1500"


def test_bulk_order():
    assert render([("pen", 10)]) == "pen x10: 1350\nTOTAL 1350"
