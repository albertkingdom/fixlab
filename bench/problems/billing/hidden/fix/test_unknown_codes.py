from bill.receipt import checkout


def test_codes_are_case_sensitive():
    assert checkout([("book", 1)], "save10") == "ERROR: unknown discount code save10"


def test_an_empty_code_is_unknown():
    assert checkout([("book", 1)], "") == "ERROR: unknown discount code "


def test_a_code_with_a_space_is_unknown():
    assert checkout([("bag", 1)], " VIP") == "ERROR: unknown discount code  VIP"
