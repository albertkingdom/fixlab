from bill.receipt import checkout


def test_vip_code():
    assert checkout([("bag", 2)], "VIP") == "bag x2: 7000\nDISCOUNT -2100\nTOTAL 4900"


def test_discount_is_floored_to_the_cent():
    assert checkout([("gum", 1)], "SAVE10") == "gum x1: 99\nDISCOUNT -9\nTOTAL 90"


def test_no_code_means_no_discount():
    assert checkout([("pen", 3), ("book", 1)]) == "pen x3: 450\nbook x1: 1200\nTOTAL 1650"
