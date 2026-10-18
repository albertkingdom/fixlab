"""庫存報表。"""

from stock.catalog import CATALOG
from stock.importer import parse_receipt
from stock.ledger import Ledger


def stock_report(receipt_lines):
    ledger = Ledger()
    for sku, units in parse_receipt(receipt_lines).items():
        ledger.receive(sku, units)
    rows = [f"{sku} {CATALOG[sku]['name']}: {ledger.on_hand(sku)}" for sku in ledger.skus()]
    total = sum(ledger.on_hand(sku) for sku in ledger.skus())
    rows.append(f"TOTAL units {total}")
    return "\n".join(rows)
