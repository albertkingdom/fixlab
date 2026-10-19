# 題目自我檢查的測試：對應 benchmark-problems 規格的 The self-check verifies every problem without calling a model。
# 用玩具題目的副本與手工改壞的版本；「結果不一致」用假的 run_group 逐次回不同結果，不靠亂數。
import json
import shutil
from pathlib import Path

import pytest

import fixlab.bench.selfcheck as selfcheck
from fixlab.bench.__main__ import main as bench_main
from fixlab.bench.grader import GroupRun
from fixlab.bench.problems import load_problem
from fixlab.bench.selfcheck import check_problem, check_problem_set

TOY_ROOT = Path(__file__).resolve().parent / "fixtures" / "bench_toy"


@pytest.fixture
def toy_root(tmp_path):
    """玩具題目的副本（放在 root 底下的 cart 資料夾），測試可以放心改壞。"""
    shutil.copytree(TOY_ROOT / "cart", tmp_path / "bench" / "cart", ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path / "bench"


def reasons_of(toy_root, repeat=2):
    return check_problem(load_problem(toy_root / "cart"), repeat=repeat).reasons


# Scenario: A correct problem passes
def test_a_correct_problem_passes():
    result = check_problem(load_problem(TOY_ROOT / "cart"), repeat=3)

    assert result.ok, result.reasons


# Scenario: A fix group that already passes is reported
def test_a_fix_group_that_already_passes_is_reported(toy_root):
    fix_test = toy_root / "cart" / "hidden" / "fix" / "test_discount.py"
    fix_test.write_text("from shop.report import render\n\n\ndef test_eleven():\n"
                        '    assert render([("pen", 11)]) == "pen x11: 1485\\nTOTAL 1485"\n')  # 原始專案也通過
    data = json.loads((toy_root / "cart" / "problem.json").read_text())
    data["hidden"]["fix"] = 1
    (toy_root / "cart" / "problem.json").write_text(json.dumps(data))

    reasons = reasons_of(toy_root)

    assert any("bug is not covered by the fix group" in reason for reason in reasons), reasons


def test_a_wrong_test_count_is_reported(toy_root):
    data = json.loads((toy_root / "cart" / "problem.json").read_text())
    data["hidden"]["keep"] = 4  # 實際只有 3 個
    (toy_root / "cart" / "problem.json").write_text(json.dumps(data))

    reasons = reasons_of(toy_root)

    assert any("3 tests ran, problem.json says 4" in reason for reason in reasons), reasons


def test_a_wrong_expected_failure_count_is_reported(toy_root):
    data = json.loads((toy_root / "cart" / "problem.json").read_text())
    data["visible"]["failing"] = 2  # 實際只失敗 1 個
    (toy_root / "cart" / "problem.json").write_text(json.dumps(data))

    assert any("1 tests fail, problem.json says 2" in reason for reason in reasons_of(toy_root))


def test_a_solution_that_does_not_fix_the_problem_is_reported(toy_root):
    shutil.copy(toy_root / "cart" / "project" / "shop" / "cart.py", toy_root / "cart" / "solution" / "shop" / "cart.py")

    reasons = reasons_of(toy_root)

    assert any("solved visible: does not pass" in reason for reason in reasons), reasons


# Scenario: A flaky problem is reported
def test_results_that_differ_between_repetitions_are_reported(monkeypatch):
    runs = iter([GroupRun(True, {"passed": 3}, ""), GroupRun(False, {"failed": 1, "passed": 2}, "")] * 100)
    monkeypatch.setattr(selfcheck, "run_group", lambda problem, workdir, group: next(runs))

    result = check_problem(load_problem(TOY_ROOT / "cart"), repeat=2)

    assert not result.ok and any("results differ between repetitions" in reason for reason in result.reasons)


# Scenario: The failure output names the buggy file
def test_a_failure_output_that_names_the_buggy_file_is_reported(toy_root):
    cart = toy_root / "cart" / "project" / "shop" / "cart.py"
    cart.write_text(cart.read_text().replace("    amount = price_of(item) * quantity\n",
                                             "    if quantity == 10:\n        raise RuntimeError('boom')\n"
                                             "    amount = price_of(item) * quantity\n"))

    reasons = reasons_of(toy_root)

    assert any("names cart.py" in reason and "bug location" in reason for reason in reasons), reasons


# Each project states its correct behavior and contains distractors（路徑要存在）
def test_a_listed_path_that_does_not_exist_is_reported(toy_root):
    data = json.loads((toy_root / "cart" / "problem.json").read_text())
    data["distractors"] = ["shop/old_helper.py"]
    (toy_root / "cart" / "problem.json").write_text(json.dumps(data))

    assert any("shop/old_helper.py" in reason for reason in reasons_of(toy_root))


# ── 題目集與 check 子命令 ─────────────────────────────────────────────────

def test_the_problem_set_must_be_exactly_the_eight_problems():
    problems = [load_problem(TOY_ROOT / "cart")]

    reasons = check_problem_set(problems)

    assert any("missing problems: inventory, calendar" in reason for reason in reasons)
    assert any("unexpected problems: cart" in reason for reason in reasons)


def test_the_check_command_exits_zero_when_every_problem_passes(capsys):
    code = bench_main(["check", "--problems-dir", str(TOY_ROOT), "--repeat", "2"])

    assert code == 0 and "cart: passed" in capsys.readouterr().out


def test_the_check_command_exits_non_zero_and_lists_the_reasons(toy_root, capsys):
    shutil.copy(toy_root / "cart" / "project" / "shop" / "cart.py", toy_root / "cart" / "solution" / "shop" / "cart.py")

    code = bench_main(["check", "--problems-dir", str(toy_root), "--repeat", "2"])

    out = capsys.readouterr().out
    assert code == 1 and "cart: FAILED" in out and "solved visible" in out
