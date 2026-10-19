"""把收貨單的文字行換算成「品號 → 件數」。"""

from stock.catalog import CATALOG


def multiplier(entry, unit):
    """一個單位等於幾件。"""
    if unit == "unit":
        return 1
    if unit == "pack":
        return entry["per_pack"]
    return entry["per_case"]


def parse_receipt(lines):
    """每行 `品號,數量,單位`，回傳 {品號: 件數}。品號不在目錄裡的行略過。"""
    received = {}
    for line in lines:
        sku, quantity, unit = line.split(",")
        entry = CATALOG.get(sku)
        if entry is None:
            continue
        received[sku] = received.get(sku, 0) + int(quantity) * multiplier(entry, unit)
    return received
