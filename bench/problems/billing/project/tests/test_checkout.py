from bill.receipt import checkout


def test_valid_code():
    assert checkout([("pen", 2)], "SAVE10") == "pen x2: 300\nDISCOUNT -30\nTOTAL 270"


def test_mistyped_code():
    assert checkout([("pen", 2)], "SAVE1O") == "ERROR: unknown discount code SAVE1O"
