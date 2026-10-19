"""UTC 與本地時間互轉。"""

from subs.clock import LOCAL_OFFSET


def to_utc(local_moment):
    return local_moment - LOCAL_OFFSET


def to_local(utc_moment):
    return utc_moment + LOCAL_OFFSET
