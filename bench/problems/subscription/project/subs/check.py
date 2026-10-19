"""訂閱有沒有到期。兩個時間都是 UTC。"""

from subs.tz import to_local


def is_active(expiry_utc, now_utc):
    return to_local(now_utc) < expiry_utc
