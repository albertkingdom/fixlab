"""把頁數限制在有效範圍內。"""


def clamp(page, last_page):
    return max(1, min(page, last_page))
