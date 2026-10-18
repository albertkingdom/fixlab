"""收據。"""

from bill.discounts import UnknownCodeError, discount_for
from bill.prices import price_of


def checkout(lines, code=None):
    rows = []
    subtotal = 0
    for sku, quantity in lines:
        amount = price_of(sku) * quantity
        subtotal += amount
        rows.append(f"{sku} x{quantity}: {amount}")
    discount = 0
    if code is not None:
        try:
            discount = discount_for(code, subtotal)
        except UnknownCodeError:
            return f"ERROR: unknown discount code {code}"
        if discount:
            rows.append(f"DISCOUNT -{discount}")
    rows.append(f"TOTAL {subtotal - discount}")
    return "\n".join(rows)
