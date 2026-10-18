from shop.report import render


def test_exactly_ten_gets_the_discount():
    assert render([("book", 10)]) == "book x10: 10800\nTOTAL 10800"


def test_eleven_gets_the_discount():
    assert render([("pen", 11)]) == "pen x11: 1485\nTOTAL 1485"


def test_discount_is_per_line_not_per_order():
    assert render([("pen", 10), ("book", 1)]) == "pen x10: 1350\nbook x1: 1200\nTOTAL 2550"
