from shop.prices import price_of

DISCOUNT_FROM = 10


def line_amount(item, quantity):
    amount = price_of(item) * quantity
    if quantity > DISCOUNT_FROM:
        amount = amount * 9 // 10
    return amount
