"""把訂閱的到期時間（本地時間的文字）換成 UTC。"""

from subs.clock import parse
from subs.tz import to_utc


def parse_expiry(text):
    return to_utc(parse(text))
