"""把任務分到優先權的桶子。"""

from taskplan.ordering import sort_key


def bucket_of(task):
    return sort_key(task)[0]


def bucket_counts(tasks):
    """回傳 [(優先權, 數量)]，優先權由大到小。"""
    counts = {}
    for task in tasks:
        counts[bucket_of(task)] = counts.get(bucket_of(task), 0) + 1
    return sorted(counts.items(), reverse=True)
