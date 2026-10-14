"""彙整一週的工時紀錄。"""

from timelog.parser import parse_duration


def weekly_total(entries):
    """entries 是工時字串的清單，回傳總時數（小時）。"""
    minutes = sum(parse_duration(entry) for entry in entries)
    return minutes / 60
