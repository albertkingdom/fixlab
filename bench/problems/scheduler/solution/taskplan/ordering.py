"""任務的排序。"""


def sort_key(task):
    """排序用的鍵：第一個元素是優先權（分桶也用它），再來是到期日，最後是名字。"""
    return (task.priority, task.due, task.name)


def execution_key(task):
    """執行順序：優先權大的先，再來到期日小的先，最後名字。"""
    return (-task.priority, task.due, task.name)


def order(tasks):
    return sorted(tasks, key=execution_key)
