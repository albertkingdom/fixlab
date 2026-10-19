"""頁數與每頁的範圍。"""


def page_count(total, size):
    if total == 0:
        return 1
    return -(-total // size)


def slice_for(page, size):
    start = (page - 1) * size
    return start, start + size
