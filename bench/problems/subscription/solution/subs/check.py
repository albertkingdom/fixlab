"""訂閱有沒有到期。兩個時間都是 UTC。"""


def is_active(expiry_utc, now_utc):
    return now_utc < expiry_utc
