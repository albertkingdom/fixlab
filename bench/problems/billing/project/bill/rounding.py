"""金額的捨去。"""


def floor_to_cent(amount_times_percent):
    """輸入是「小計乘百分比」，除以 100 之後無條件捨去到分。"""
    return amount_times_percent // 100
