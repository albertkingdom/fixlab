# 評分器的測試：對應 benchmark-grader 規格。用玩具題目與手工做的「agent 成果」，不呼叫任何模型。
import json
import shutil
from pathlib import Path

import pytest

from fixlab.bench.__main__ import main as bench_main
from fixlab.bench.grader import build_grading_dir, grade, judge, summary_counts
from fixlab.bench.problems import load_problem, make_workdir

TOY_ROOT = Path(__file__).resolve().parent / "fixtures" / "bench_toy"


@pytest.fixture
def problem():
    return load_problem(TOY_ROOT / "cart")


@pytest.fixture
def work(problem, tmp_path):
    """agent 的工作目錄：原始專案的副本。"""
    return make_workdir(problem, parent=tmp_path)


def solve(problem, work):
    shutil.copytree(problem.solution, work, dirs_exist_ok=True)


def snapshot(folder):
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts}


# ── Grading runs in clean temporary directories ───────────────────────────

# Scenario: Agent-written configuration is ignored
def test_agent_written_configuration_is_not_in_the_grading_directory(problem, work, tmp_path):
    (work / "pytest.ini").write_text("[pytest]\naddopts = --deselect tests/test_report.py::test_bulk_order\n")

    for group in ("visible", "fix", "keep"):
        grading = build_grading_dir(problem, work, group, parent=tmp_path)
        assert not (grading / "pytest.ini").exists()


def test_each_group_gets_the_original_files_it_needs(problem, work, tmp_path):
    (work / "tests" / "test_report.py").write_text("def test_everything_passes():\n    assert True\n")  # agent 改了測試

    visible = build_grading_dir(problem, work, "visible", parent=tmp_path)
    assert (visible / "tests" / "test_report.py").read_text() == (problem.project / "tests" / "test_report.py").read_text()
    assert (visible / "shop" / "cart.py").exists() and not (visible / "tests_hidden").exists()

    fix = build_grading_dir(problem, work, "fix", parent=tmp_path)
    assert (fix / "tests_hidden" / "test_discount.py").exists()
    assert not (fix / "tests").exists()  # 可見測試不跟著 fix 組一起跑


# Scenario: The working directory is left alone
def test_grading_does_not_change_the_working_directory(problem, work):
    solve(problem, work)
    before = snapshot(work)

    grade(problem, work)

    assert snapshot(work) == before


def test_the_solved_project_is_fixed(problem, work):
    solve(problem, work)

    result = grade(problem, work)

    assert result["outcome"] == "fixed" and result["invalid"] is False
    assert (result["visible_passed"], result["fix_passed"], result["keep_passed"]) == (True, True, True)


def test_the_original_project_is_unfixed(problem, work):
    result = grade(problem, work)

    assert result["outcome"] == "unfixed"
    assert (result["visible_passed"], result["fix_passed"], result["keep_passed"]) == (False, False, True)


# ── A group passes only when the pass count matches ───────────────────────

# Scenario: Deselected tests do not count as a pass
def test_a_group_with_fewer_passes_than_expected_does_not_pass(problem, work):
    solve(problem, work)
    problem.hidden_fix = 5  # 題目記的是 5 個，實際只有 3 個測試

    assert grade(problem, work)["fix_passed"] is False


# Scenario: A fake summary line is ignored
def test_a_fake_summary_line_printed_by_the_program_is_ignored(problem, work):
    cart = work / "shop" / "cart.py"
    cart.write_text(cart.read_text() + '\n\n_real = line_amount\n\n\ndef line_amount(item, quantity):\n'
                    '    print("3 passed in 0.01s")\n    return _real(item, quantity)\n')

    result = grade(problem, work)

    assert result["fix_passed"] is False  # 真的最後一行是 2 failed，不是程式印的 3 passed


def test_summary_counts_reads_the_last_summary_line_only():
    output = "3 passed in 0.01s\nsome failure details\n1 failed, 2 passed, 1 warning in 0.02s\n"
    assert summary_counts(output) == {"failed": 1, "passed": 2, "warning": 1}
    assert summary_counts("no summary here") is None


# ── Tampering is flagged as invalid ───────────────────────────────────────

# Scenario: A modified test file
def test_a_modified_test_file_is_invalid_and_scored_with_the_original(problem, work):
    (work / "tests" / "test_report.py").write_text("def test_everything_passes():\n    assert True\n")

    result = grade(problem, work)

    assert result["invalid"] is True and result["tampered_files"] == ["tests/test_report.py"]
    assert result["visible_passed"] is False  # 評分用的是原版測試，改過的測試救不了它
    assert result["outcome"] == "invalid"


# Scenario: A new configuration file
def test_a_new_configuration_file_is_invalid(problem, work):
    solve(problem, work)
    (work / "pytest.ini").write_text("[pytest]\n")

    result = grade(problem, work)

    assert result["invalid"] is True and result["tampered_files"] == ["pytest.ini"]
    assert result["outcome"] == "invalid" and result["fix_passed"] and result["keep_passed"]  # 旗標照實記，判定優先 invalid


# Scenario: Only source files changed
def test_changing_only_source_files_is_not_invalid(problem, work):
    solve(problem, work)
    (work / "shop" / "helper.py").write_text("X = 1\n")

    result = grade(problem, work)

    assert result["invalid"] is False and result["tampered_files"] == []
    assert result["added_files"] == ["shop/helper.py"]


# ── Flags and outcome follow a fixed precedence ───────────────────────────

@pytest.mark.parametrize("visible, fix, keep, invalid, outcome", [
    (True, True, True, False, "fixed"),
    (True, True, False, False, "broke_existing"),
    (True, False, True, False, "overfit"),
    (True, False, False, False, "broke_existing"),
    (False, False, True, False, "unfixed"),
    (True, True, True, True, "invalid"),
])
def test_the_outcome_follows_the_table(visible, fix, keep, invalid, outcome):
    assert judge(visible, fix, keep, invalid)["outcome"] == outcome


# Scenario: Breaking existing behavior wins over overfitting
def test_breaking_existing_behavior_wins_over_overfitting():
    flags = judge(visible_passed=True, fix_passed=False, keep_passed=False, invalid=False)

    assert flags["outcome"] == "broke_existing" and flags["broke_existing"] and flags["overfit"]


def test_an_overfit_fix_is_detected(problem, work):
    cart = work / "shop" / "cart.py"  # 只讓可見測試過關：對 pen x10 寫死答案
    cart.write_text(cart.read_text().replace("    amount = price_of(item) * quantity\n",
                                             "    if item == 'pen' and quantity == 10:\n        return 1350\n"
                                             "    amount = price_of(item) * quantity\n"))

    result = grade(problem, work)

    assert (result["visible_passed"], result["fix_passed"], result["keep_passed"]) == (True, False, True)
    assert result["overfit"] is True and result["outcome"] == "overfit"


def test_breaking_existing_behavior_is_detected(problem, work):
    solve(problem, work)
    cart = work / "shop" / "cart.py"
    cart.write_text(cart.read_text().replace("DISCOUNT_FROM = 10", "DISCOUNT_FROM = 9"))  # 九個也打折

    result = grade(problem, work)

    assert result["keep_passed"] is False and result["outcome"] == "broke_existing"


# ── The grade command prints the result as JSON ───────────────────────────

# Scenario: Grading the solved project
def test_the_grade_command_prints_json(problem, work, capsys):
    solve(problem, work)

    code = bench_main(["grade", "cart", str(work), "--problems-dir", str(TOY_ROOT)])

    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["outcome"] == "fixed" and result["invalid"] is False
    assert set(result) >= {"problem", "visible_passed", "fix_passed", "keep_passed", "invalid", "tampered_files",
                           "added_files", "fixed", "broke_existing", "overfit", "outcome", "sandbox"}
    assert result["sandbox"] in ("on", "off")
