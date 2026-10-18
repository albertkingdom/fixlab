"""舊版的分頁計算，已經停用，留著對照。沒有任何地方匯入它。"""


def old_page_count(total, size):
    pages = total // size
    if total % size:
        pages += 1
    return pages or 1
