"""benchmark 的題目：每題一個資料夾，載入、驗證、建立給 agent 的工作目錄、計算內容摘要。

一個題目資料夾長這樣：

    problem.json     題目的資料（領域、bug 類型、bug 所在的檔案、各組測試的數量）
    project/         給 agent 的初始專案：原始碼、規格（README）、可見測試
    solution/        標準解：只放有改動的檔案，覆蓋在 project 上
    hidden/fix/      隱藏測試：bug 真的修好了嗎
    hidden/keep/     隱藏測試：原本正常的功能還正常嗎

agent 只會拿到 project 的副本，hidden 與 solution 永遠不在它看得到的路徑裡。
"""

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fixlab.workspace import FIXLAB_ROOT

PROBLEMS_DIR = FIXLAB_ROOT / "bench" / "problems"

# benchmark 固定這八題（階段 3 的提案）
EXPECTED_IDS = ("inventory", "calendar", "settings", "billing", "subscription", "paging", "scheduler", "permissions")

IGNORED_NAMES = ("__pycache__", ".pytest_cache")  # 複製與計算摘要時略過


class ProblemError(ValueError):
    """題目資料夾不合格。訊息一定先寫題目的名字。"""


@dataclass
class Problem:
    id: str
    domain: str
    bug_type: str
    bug_files: list       # project 裡 bug 所在的檔案
    distractors: list     # project 裡的干擾檔
    visible_total: int    # 可見測試的數量
    visible_failing: int  # 原始專案有幾個可見測試失敗
    hidden_fix: int       # fix 組的測試數量
    hidden_keep: int      # keep 組的測試數量
    folder: Path

    @property
    def project(self) -> Path:
        return self.folder / "project"

    @property
    def solution(self) -> Path:
        return self.folder / "solution"

    @property
    def fix_tests(self) -> Path:
        return self.folder / "hidden" / "fix"

    @property
    def keep_tests(self) -> Path:
        return self.folder / "hidden" / "keep"


def load_problem(folder) -> Problem:
    """讀一個題目資料夾。缺資料夾或缺鍵時丟出指名題目與缺項的 ProblemError。"""
    folder = Path(folder)
    name = folder.name
    for item in ("problem.json", "project", "solution", "hidden/fix", "hidden/keep"):
        if not (folder / item).exists():
            raise ProblemError(f"{name}: missing {item}")

    try:
        data = json.loads((folder / "problem.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProblemError(f"{name}: problem.json is not valid JSON ({error})") from None

    for key in ("id", "domain", "bug_type", "bug_files", "distractors", "visible", "hidden"):
        if key not in data:
            raise ProblemError(f"{name}: problem.json lacks the key {key!r}")
    for key in ("total", "failing"):
        if key not in data["visible"]:
            raise ProblemError(f"{name}: problem.json lacks the key 'visible.{key}'")
    for key in ("fix", "keep"):
        if key not in data["hidden"]:
            raise ProblemError(f"{name}: problem.json lacks the key 'hidden.{key}'")
    if data["id"] != name:
        raise ProblemError(f"{name}: problem.json says the id is {data['id']!r}, but the folder is named {name!r}")

    return Problem(
        id=data["id"], domain=data["domain"], bug_type=data["bug_type"],
        bug_files=list(data["bug_files"]), distractors=list(data["distractors"]),
        visible_total=data["visible"]["total"], visible_failing=data["visible"]["failing"],
        hidden_fix=data["hidden"]["fix"], hidden_keep=data["hidden"]["keep"],
        folder=folder)


def load_all(root=PROBLEMS_DIR) -> list[Problem]:
    """root 底下每個子資料夾都是一題，依名稱排序。"""
    return [load_problem(folder) for folder in sorted(Path(root).iterdir()) if folder.is_dir()]


def make_workdir(problem: Problem, parent=None) -> Path:
    """給 agent 的工作目錄：project 的暫存副本，只有 project 的內容。呼叫的人負責用完刪掉。"""
    workdir = Path(tempfile.mkdtemp(prefix=f"fixlab-{problem.id}-", dir=parent)).resolve()
    shutil.copytree(problem.project, workdir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*IGNORED_NAMES))
    return workdir


def problem_digest(problem: Problem) -> str:
    """題目所有檔案的 SHA-256（路徑加內容，依路徑排序）。任何一個檔案改變，摘要就不同，
    所以一筆結果可以對到產生它的那一版題目。"""
    hasher = hashlib.sha256()
    for path in sorted(problem.folder.rglob("*")):
        relative = path.relative_to(problem.folder)
        if not path.is_file() or any(part in IGNORED_NAMES for part in relative.parts) or path.suffix == ".pyc":
            continue
        hasher.update(relative.as_posix().encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return hasher.hexdigest()
