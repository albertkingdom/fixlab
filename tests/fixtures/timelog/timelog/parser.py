"""把工時字串換成分鐘數。
支援 "2h"、"45m"、"1h30m" 這類寫法。"""

import re


def parse_duration(text):
    """回傳 text 代表的分鐘數，格式不對時拋 ValueError。"""
    text = text.strip()
    if not re.fullmatch(r"(\d+[hm])+", text):
        raise ValueError(f"invalid duration: {text!r}")
    units = [re.match(r"(\d+)([hm])", text).groups()]
    return sum(int(number) * (60 if unit == "h" else 1) for number, unit in units)
