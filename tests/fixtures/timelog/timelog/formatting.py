"""把分鐘數格式化成 "1h30m" 這類字串，給報表顯示用。"""


def format_duration(minutes):
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours}h{rest}m"
    if hours:
        return f"{hours}h"
    return f"{rest}m"
