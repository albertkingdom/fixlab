"""舊版的算法，已經沒有人使用，留著當參考。"""


def old_line_amount(price, quantity):
    if quantity >= 10:
        return price * quantity * 9 // 10
    return price * quantity
