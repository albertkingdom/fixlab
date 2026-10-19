"""任務的排序。"""


def sort_key(task):
    """排序用的鍵：第一個元素是優先權（分桶也用它），再來是到期日，最後是名字。"""
    return (task.priority, task.due, task.name)


def order(tasks):
    return sorted(tasks, key=sort_key)
