"""時間的共同定義：本地時間比 UTC 快 8 小時。全部用沒有時區資訊的 datetime，不看機器的時區。"""

from datetime import datetime, timedelta

LOCAL_OFFSET = timedelta(hours=8)
FORMAT = "%Y-%m-%d %H:%M"


def parse(text):
    return datetime.strptime(text, FORMAT)


def format_time(moment):
    return moment.strftime(FORMAT)
