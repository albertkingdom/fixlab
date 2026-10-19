"""找出時間重疊的活動。"""

from itertools import combinations


def overlaps(first, second):
    return first.start <= second.end and second.start <= first.end


def find_conflicts(events):
    """回傳所有重疊的活動配對，每一對的名字依字母排序。"""
    pairs = []
    for first, second in combinations(events, 2):
        if overlaps(first, second):
            pairs.append(tuple(sorted((first.name, second.name))))
    return sorted(pairs)
