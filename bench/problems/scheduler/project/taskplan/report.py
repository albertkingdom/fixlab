"""排程報表。"""

from taskplan.ordering import order
from taskplan.queue import bucket_counts


def execution_order(tasks):
    return [task.name for task in order(tasks)]


def summary(tasks):
    rows = [f"{number}. {task.name} (P{task.priority}, due {task.due})" for number, task in enumerate(order(tasks), start=1)]
    buckets = " ".join(f"P{priority}={count}" for priority, count in bucket_counts(tasks))
    rows.append(f"Buckets: {buckets}".rstrip())
    return "\n".join(rows)
