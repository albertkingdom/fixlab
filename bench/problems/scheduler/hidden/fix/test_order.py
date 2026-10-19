from taskplan.report import execution_order
from taskplan.tasks import Task


def test_priority_beats_due_day():
    tasks = [Task("a", 1, 1), Task("b", 5, 99), Task("c", 3, 2)]
    assert execution_order(tasks) == ["b", "c", "a"]


def test_ties_go_by_due_then_name():
    tasks = [Task("zeta", 2, 4), Task("alpha", 2, 4), Task("mid", 2, 1)]
    assert execution_order(tasks) == ["mid", "alpha", "zeta"]


def test_a_single_task():
    assert execution_order([Task("only", 0, 0)]) == ["only"]
