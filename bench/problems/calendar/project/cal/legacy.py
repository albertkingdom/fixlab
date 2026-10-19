"""舊版的衝突檢查，已經停用，留著對照。沒有任何地方匯入它。"""


def old_overlap(a_start, a_end, b_start, b_end):
    return not (a_end < b_start or b_end < a_start)
