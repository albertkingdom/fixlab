"""訂閱狀態報表。"""

from subs.check import is_active
from subs.clock import format_time, parse
from subs.parse import parse_expiry
from subs.tz import to_local


def status_report(subscriptions, now_text):
    now_utc = parse(now_text)
    rows = []
    for name, expiry_text in sorted(subscriptions):
        expiry_utc = parse_expiry(expiry_text)
        if is_active(expiry_utc, now_utc):
            rows.append(f"{name}: active until {format_time(to_local(expiry_utc))}")
        else:
            rows.append(f"{name}: expired")
    return "\n".join(rows)
