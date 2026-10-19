"""舊版的收貨匯入，已經改用新的匯入程式，留著對照。沒有任何地方匯入它。"""

CASE_SIZES = {"A100": 100, "B200": 24, "C300": 50}


def parse_receipt_v1(lines):
    received = {}
    for line in lines:
        sku, quantity, unit = line.split(",")
        size = CASE_SIZES.get(sku, 1) if unit == "case" else 1
        received[sku] = received.get(sku, 0) + int(quantity) * size
    return received
