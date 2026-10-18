"""單價，單位是分。"""

PRICES = {"pen": 150, "book": 1200, "bag": 3500, "gum": 99}


def price_of(sku):
    try:
        return PRICES[sku]
    except KeyError:
        raise ValueError(f"unknown item: {sku}") from None
