from taskplan.report import summary
from taskplan.tasks import Task


def test_buckets_list_priorities_from_high_to_low():
    tasks = [Task("a", 3, 1), Task("b", 3, 2), Task("c", 1, 1)]
    assert summary(tasks).splitlines()[-1] == "Buckets: P3=2 P1=1"


def test_no_tasks():
    assert summary([]) == "Buckets:"


def test_one_priority_only():
    tasks = [Task("a", 2, 1), Task("b", 2, 2)]
    assert summary(tasks) == "1. a (P2, due 1)\n2. b (P2, due 2)\nBuckets: P2=2"
