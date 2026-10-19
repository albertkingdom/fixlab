from shop.cart import line_amount


def render(lines):
    rows = []
    total = 0
    for item, quantity in lines:
        amount = line_amount(item, quantity)
        total += amount
        rows.append(f"{item} x{quantity}: {amount}")
    rows.append(f"TOTAL {total}")
    return "\n".join(rows)
