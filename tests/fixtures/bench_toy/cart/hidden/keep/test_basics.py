from shop.report import render


def test_nine_has_no_discount():
    assert render([("pen", 9)]) == "pen x9: 1350\nTOTAL 1350"


def test_several_lines():
    assert render([("pen", 1), ("book", 2)]) == "pen x1: 150\nbook x2: 2400\nTOTAL 2550"


def test_empty_cart():
    assert render([]) == "TOTAL 0"
