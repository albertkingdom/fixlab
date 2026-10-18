from taskplan.report import summary
from taskplan.tasks import Task


def test_same_priority_goes_by_due_day():
    tasks = [Task("write", 2, 5), Task("review", 2, 3)]
    assert summary(tasks) == "1. review (P2, due 3)\n2. write (P2, due 5)\nBuckets: P2=2"


def test_higher_priority_goes_first():
    tasks = [Task("write", 1, 1), Task("deploy", 3, 9)]
    assert summary(tasks) == "1. deploy (P3, due 9)\n2. write (P1, due 1)\nBuckets: P3=1 P1=1"
