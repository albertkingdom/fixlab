"""假日的計算。"""

from datetime import date, timedelta

FIXED_HOLIDAYS = {(1, 1), (12, 25)}


def is_holiday(day):
    return (day.month, day.day) in FIXED_HOLIDAYS


def next_business_day(day):
    """下一個不是週末也不是假日的日子。"""
    following = day + timedelta(days=1)
    while following.weekday() >= 5 or is_holiday(following):
        following += timedelta(days=1)
    return following
