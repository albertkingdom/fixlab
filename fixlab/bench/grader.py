"""評分器：在乾淨的暫存目錄裡，用 agent 改完的原始碼加原版測試，對隱藏測試評分。

為什麼不直接在 agent 的工作目錄跑隱藏測試：agent 能放進設定檔、conftest 或別的檔案影響結果。
這裡的做法是三次獨立評分（可見測試、fix 組、keep 組），每次新建暫存目錄，只帶 agent 的原始碼，
測試與設定一律用題目資料夾裡的原版。測試用 Workspace 的 run_tests 工具跑，
所以沿用同一份固定的 pytest 參數、沙箱與環境變數，不另寫一份。

限制（見 README）：被測的程式與 pytest 在同一個行程，仍可能偽造結果。這裡只降低風險：
只認 pytest 輸出的最後一行摘要、通過數要和題目記的數量一致、不自動載入外掛。
"""

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePath

from fixlab.bench.problems import IGNORED_NAMES, Problem
from fixlab.display import pytest_summary
from fixlab.sandbox import sandbox_available
from fixlab.tools import register_tools
from fixlab.workspace import Workspace, iter_files, looks_like_test_file

CONFIG_NAMES = ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", "conftest.py")
HIDDEN_FOLDER = "tests_hidden"  # fix 與 keep 那兩次，隱藏測試放在暫存目錄的這個資料夾，目標也只有它


def is_test_or_config(relative) -> bool:
    """這個相對路徑是測試檔或設定檔嗎？評分時它們一律用原版，不用 agent 的。"""
    return looks_like_test_file(relative) or PurePath(relative).name in CONFIG_NAMES


def copy_file(source: Path, destination_root: Path, relative) -> None:
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_grading_dir(problem: Problem, workdir: Path, group: str, parent=None) -> Path:
    """為一次評分新建暫存目錄。group 是 "visible"、"fix" 或 "keep"。呼叫的人負責刪掉。"""
    grading = Path(tempfile.mkdtemp(prefix="fixlab-grade-", dir=parent)).resolve()

    # agent 的檔案：測試檔與設定檔不帶，agent 加的 pytest.ini、改過的測試都進不來
    for source in iter_files(workdir):
        relative = source.relative_to(workdir)
        if not is_test_or_config(relative):
            copy_file(source, grading, relative)

    if group == "visible":
        # 原版的測試檔（含 conftest.py 與 tests 資料夾裡的資料檔），原路徑
        for source in iter_files(problem.project):
            relative = source.relative_to(problem.project)
            if looks_like_test_file(relative):
                copy_file(source, grading, relative)
    else:
        # 只放原版 conftest.py（如果有）與這一組隱藏測試，所以可見測試不會一起跑
        conftest = problem.project / "conftest.py"
        if conftest.is_file():
            copy_file(conftest, grading, "conftest.py")
        hidden = problem.fix_tests if group == "fix" else problem.keep_tests
        shutil.copytree(hidden, grading / HIDDEN_FOLDER, ignore=shutil.ignore_patterns(*IGNORED_NAMES))
    return grading


def summary_counts(output: str) -> dict | None:
    """pytest 輸出最後一行摘要的各項數量，例如 {"failed": 1, "passed": 4}；找不到摘要就是 None。
    只讀最後一行：被測的程式可以先印一行假的摘要，真的在最後。"""
    line = pytest_summary(output)
    if line is None:
        return None
    body = line.split(" in ")[0]
    return {word: int(number) for number, word in re.findall(r"(\d+) (\w+)", body)}


@dataclass
class GroupRun:
    """一組測試跑一次的結果。"""
    passed: bool       # 算通過嗎（見 run_group）
    counts: dict | None  # 最後一行摘要的各項數量，沒有摘要就是 None
    output: str        # run_tests 的完整輸出

    def signature(self) -> tuple:
        """重跑時用來比較「結果有沒有變」。"""
        return (self.passed, tuple(sorted(self.counts.items())) if self.counts else None)


def run_group(problem: Problem, workdir: Path, group: str) -> GroupRun:
    """在乾淨的暫存目錄跑一組測試。算通過：run_tests 回報通過，而且最後一行摘要的通過數等於題目記的數量、
    沒有失敗與錯誤。數量比對用來擋「用 deselect 少跑幾個再印全過」。"""
    expected = {"visible": problem.visible_total, "fix": problem.hidden_fix, "keep": problem.hidden_keep}[group]
    grading = build_grading_dir(problem, workdir, group)
    try:
        workspace = Workspace(grading, protect_tests=True)
        register_tools(workspace)
        result = workspace.call("run_tests", {"target": "." if group == "visible" else HIDDEN_FOLDER})
    finally:
        shutil.rmtree(grading, ignore_errors=True)

    counts = summary_counts(result.output)
    if not result.flags.get("tests_passed") or counts is None:
        return GroupRun(False, counts, result.output)
    broken = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
    return GroupRun(counts.get("passed") == expected and broken == 0, counts, result.output)


def group_passes(problem: Problem, workdir: Path, group: str) -> bool:
    return run_group(problem, workdir, group).passed


def find_tampered(problem: Problem, workdir: Path) -> list:
    """agent 的工作目錄裡，與原版 project 不同、或原版沒有的測試檔與設定檔。"""
    tampered = []
    for source in iter_files(workdir):
        relative = source.relative_to(workdir)
        if not is_test_or_config(relative):
            continue
        original = problem.project / relative
        if not original.is_file() or original.read_bytes() != source.read_bytes():
            tampered.append(relative.as_posix())
    return sorted(tampered)


def find_added(problem: Problem, workdir: Path) -> list:
    """agent 新增的非測試檔。只是證據，給人查看。"""
    added = []
    for source in iter_files(workdir):
        relative = source.relative_to(workdir)
        if not is_test_or_config(relative) and not (problem.project / relative).exists():
            added.append(relative.as_posix())
    return sorted(added)


def judge(visible_passed: bool, fix_passed: bool, keep_passed: bool, invalid: bool) -> dict:
    """由量到的旗標推出衍生旗標與總結。outcome 依這個順序找第一個成立的：
    invalid、broke_existing、fixed、overfit，都不是就是 unfixed。"""
    fixed = fix_passed and keep_passed
    broke_existing = not keep_passed
    overfit = visible_passed and not fix_passed
    if invalid:
        outcome = "invalid"
    elif broke_existing:
        outcome = "broke_existing"
    elif fixed:
        outcome = "fixed"
    elif overfit:
        outcome = "overfit"
    else:
        outcome = "unfixed"
    return {"fixed": fixed, "broke_existing": broke_existing, "overfit": overfit, "outcome": outcome}


def grade(problem: Problem, workdir) -> dict:
    """對 agent 改完的工作目錄評分。不修改工作目錄。"""
    workdir = Path(workdir)
    tampered = find_tampered(problem, workdir)
    visible = group_passes(problem, workdir, "visible")
    fix = group_passes(problem, workdir, "fix")
    keep = group_passes(problem, workdir, "keep")
    result = {
        "problem": problem.id,
        "visible_passed": visible, "fix_passed": fix, "keep_passed": keep,
        "invalid": bool(tampered), "tampered_files": tampered,
        "added_files": find_added(problem, workdir),
    }
    result.update(judge(visible, fix, keep, invalid=bool(tampered)))
    result["sandbox"] = "on" if sandbox_available() else "off"
    return result
