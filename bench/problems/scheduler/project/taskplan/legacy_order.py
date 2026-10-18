"""舊版的排序，已經停用，留著對照。沒有任何地方匯入它。"""


def old_compare(a, b):
    if a.priority != b.priority:
        return b.priority - a.priority
    return a.due - b.due
