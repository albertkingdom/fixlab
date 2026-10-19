"""題目自我檢查：不呼叫任何模型，只用 pytest 驗證題目做對了。

對每一題檢查：
  1. bug_files 與 distractors 列的路徑都在 project 裡。
  2. 原始 project：可見測試失敗的數量等於題目記的、至少一個 fix 測試失敗、keep 全過、各組測試數量與題目記的一致。
  3. 套上標準解之後：可見、fix、keep 三組全過。
  4. 以上每一種執行都重跑 repeat 次（預設 20），結果必須完全一樣，不然題目會 flaky。
  5. 原始 project 的可見測試失敗輸出不能出現 bug_files 的檔名：失敗輸出不能指出 bug 的位置。
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from fixlab.bench.grader import run_group
from fixlab.bench.problems import EXPECTED_IDS, Problem, make_workdir

GROUPS = ("visible", "fix", "keep")
OUTCOME_WORDS = ("passed", "failed", "error", "errors", "skipped", "xfailed", "xpassed")
DEFAULT_REPEAT = 20


@dataclass
class CheckResult:
    problem: str
    reasons: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons


def total_tests(counts: dict | None) -> int | None:
    """摘要裡所有測試結果加起來；沒有摘要就是 None。"""
    if counts is None:
        return None
    return sum(counts.get(word, 0) for word in OUTCOME_WORDS)


def failures(counts: dict | None) -> int:
    counts = counts or {}
    return counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)


def check_listed_paths(problem: Problem) -> list:
    reasons = []
    for relative in problem.bug_files + problem.distractors:
        if not (problem.project / relative).exists():
            reasons.append(f"listed path does not exist in project: {relative}")
    return reasons


def check_problem(problem: Problem, repeat: int = DEFAULT_REPEAT) -> CheckResult:
    result = CheckResult(problem.id, check_listed_paths(problem))

    original = make_workdir(problem)
    solved = make_workdir(problem)
    shutil.copytree(problem.solution, solved, dirs_exist_ok=True)
    try:
        runs = {}  # (版本, 組) → 重跑 repeat 次的結果
        for variant, workdir in (("original", original), ("solved", solved)):
            for group in GROUPS:
                runs[(variant, group)] = [run_group(problem, workdir, group) for _ in range(repeat)]
    finally:
        shutil.rmtree(original, ignore_errors=True)
        shutil.rmtree(solved, ignore_errors=True)

    # 4. 重跑結果要一樣
    for (variant, group), group_runs in runs.items():
        if any(run.signature() != group_runs[0].signature() for run in group_runs[1:]):
            result.reasons.append(f"{variant} {group}: results differ between repetitions (flaky)")
    if result.reasons and any("flaky" in reason for reason in result.reasons):
        return result  # 結果不穩，後面的比對沒有意義

    first = {key: group_runs[0] for key, group_runs in runs.items()}
    expected_total = {"visible": problem.visible_total, "fix": problem.hidden_fix, "keep": problem.hidden_keep}
    for (variant, group), run in first.items():
        if run.counts is None:
            result.reasons.append(f"{variant} {group}: no pytest summary in the output")
        elif total_tests(run.counts) != expected_total[group]:
            result.reasons.append(f"{variant} {group}: {total_tests(run.counts)} tests ran, problem.json says {expected_total[group]}")

    # 2. 原始 project
    visible = first[("original", "visible")]
    if visible.counts is not None and failures(visible.counts) != problem.visible_failing:
        result.reasons.append(f"original visible: {failures(visible.counts)} tests fail, problem.json says {problem.visible_failing}")
    fix = first[("original", "fix")]
    if fix.counts is not None and failures(fix.counts) == 0:
        result.reasons.append("original fix: all fix tests pass, so the bug is not covered by the fix group")
    keep = first[("original", "keep")]
    if keep.counts is not None and not keep.passed:
        result.reasons.append("original keep: the keep group does not pass on the original project")

    # 3. 標準解
    for group in GROUPS:
        if not first[("solved", group)].passed:
            result.reasons.append(f"solved {group}: does not pass with the solution applied")

    # 5. 失敗輸出不能指出 bug 的位置
    for relative in problem.bug_files:
        name = Path(relative).name
        if name in visible.output:
            result.reasons.append(f"original visible: the failure output names {name}, so the failure points at the bug location")
    return result


def check_problem_set(problems: list) -> list:
    """benchmark 要剛好是固定的八題。回傳不符的說明。"""
    found = {problem.id for problem in problems}
    reasons = []
    missing = [name for name in EXPECTED_IDS if name not in found]
    extra = sorted(found - set(EXPECTED_IDS))
    if missing:
        reasons.append(f"missing problems: {', '.join(missing)}")
    if extra:
        reasons.append(f"unexpected problems: {', '.join(extra)}")
    return reasons
