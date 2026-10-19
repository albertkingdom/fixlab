# 題目格式與載入的測試：對應 benchmark-problems 規格。用 tests/fixtures/bench_toy 的玩具題目，不呼叫任何模型。
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fixlab.bench.problems import ProblemError, load_all, load_problem, make_workdir, problem_digest

TOY_ROOT = Path(__file__).resolve().parent / "fixtures" / "bench_toy"
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", "/dev/null", "--rootdir=."]


@pytest.fixture
def toy_copy(tmp_path):
    """玩具題目的副本，測試可以放心改。"""
    shutil.copytree(TOY_ROOT / "cart", tmp_path / "cart", ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path / "cart"


def files_under(folder):
    return {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}


# Scenario: Loading a problem
def test_a_problem_is_loaded_with_its_data():
    problem = load_problem(TOY_ROOT / "cart")

    assert problem.id == "cart" and problem.bug_files == ["shop/cart.py"] and problem.distractors == ["shop/legacy.py"]
    assert (problem.visible_total, problem.visible_failing) == (2, 1)
    assert (problem.hidden_fix, problem.hidden_keep) == (3, 3)


def test_load_all_returns_every_problem_in_the_folder():
    assert [problem.id for problem in load_all(TOY_ROOT)] == ["cart"]


# Scenario: A malformed problem is rejected
def test_a_missing_folder_is_rejected_with_the_problem_and_the_item(toy_copy):
    shutil.rmtree(toy_copy / "hidden" / "keep")

    with pytest.raises(ProblemError, match=r"cart: missing hidden/keep"):
        load_problem(toy_copy)


def test_a_missing_key_is_rejected_with_the_problem_and_the_key(toy_copy):
    data = json.loads((toy_copy / "problem.json").read_text(encoding="utf-8"))
    del data["bug_files"]
    (toy_copy / "problem.json").write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ProblemError, match=r"cart: problem.json lacks the key 'bug_files'"):
        load_problem(toy_copy)


def test_an_id_that_differs_from_the_folder_name_is_rejected(toy_copy):
    data = json.loads((toy_copy / "problem.json").read_text(encoding="utf-8"))
    data["id"] = "other"
    (toy_copy / "problem.json").write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ProblemError, match=r"cart: .*'other'"):
        load_problem(toy_copy)


# Scenario: The working directory holds only the project
def test_the_working_directory_holds_only_the_project_files(tmp_path):
    problem = load_problem(TOY_ROOT / "cart")

    workdir = make_workdir(problem, parent=tmp_path)

    assert files_under(workdir) == files_under(problem.project)
    assert not any(name.startswith(("hidden", "solution")) or name == "problem.json" for name in files_under(workdir))


# Scenario: Editing a hidden test changes the digest
def test_the_digest_changes_when_a_hidden_test_changes(toy_copy):
    before = problem_digest(load_problem(toy_copy))
    assert problem_digest(load_problem(toy_copy)) == before  # 沒改就不變

    test_file = toy_copy / "hidden" / "fix" / "test_discount.py"
    test_file.write_text(test_file.read_text(encoding="utf-8").replace("10800", "10801"), encoding="utf-8")

    assert problem_digest(load_problem(toy_copy)) != before


# 2.2 玩具題目照設計運作：原始專案的可見測試失敗一個、fix 組有失敗、keep 組全過；標準解套上後三組全過
def run_group(workdir, target):
    return subprocess.run([*PYTEST, "--", target], cwd=workdir, capture_output=True, text=True, timeout=60)


def with_group(workdir, tests_folder):
    """把一組隱藏測試放進工作目錄的 tests_hidden（先清掉上一組）。"""
    shutil.rmtree(workdir / "tests_hidden", ignore_errors=True)
    shutil.copytree(tests_folder, workdir / "tests_hidden", ignore=shutil.ignore_patterns("__pycache__"))
    return workdir


def test_the_toy_problem_fails_as_designed_and_the_solution_passes(tmp_path):
    problem = load_problem(TOY_ROOT / "cart")
    original = make_workdir(problem, parent=tmp_path)
    solved = make_workdir(problem, parent=tmp_path)
    shutil.copytree(problem.solution, solved, dirs_exist_ok=True)

    assert "1 failed, 1 passed" in run_group(original, "tests").stdout
    assert "2 failed, 1 passed" in run_group(with_group(original, problem.fix_tests), "tests_hidden").stdout
    assert "3 passed" in run_group(with_group(original, problem.keep_tests), "tests_hidden").stdout

    assert "2 passed" in run_group(solved, "tests").stdout
    assert "3 passed" in run_group(with_group(solved, problem.fix_tests), "tests_hidden").stdout
    assert "3 passed" in run_group(with_group(solved, problem.keep_tests), "tests_hidden").stdout


def test_fixlab_does_not_collect_the_benchmark_problems():
    """題目裡的測試本來就會失敗，fixlab 自己的 pytest 不能收集它們。"""
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                            cwd=root, capture_output=True, text=True, timeout=60)

    assert "bench/problems" not in result.stdout
    assert "test_bench_problems.py" in result.stdout
