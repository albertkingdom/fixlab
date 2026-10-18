"""折扣碼。值是折扣的百分比。"""

from bill.rounding import floor_to_cent

RATES = {"SAVE10": 10, "SAVE20": 20, "VIP": 30}


class UnknownCodeError(ValueError):
    pass


def percent_for(code):
    try:
        return RATES[code]
    except KeyError:
        return 0


def discount_for(code, subtotal):
    return floor_to_cent(subtotal * percent_for(code))
