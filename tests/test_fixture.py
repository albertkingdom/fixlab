"""檢查範例專案 timelog 的 bug 照設計運作。

未修時恰好 1 個測試失敗；只改 parser.py 的一個運算式就全數通過。
pytest 指令與 run_tests 相同，所以這裡的結果就是 agent 會看到的結果。
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "timelog"
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
          "-c", "/dev/null", "--rootdir=.", "--confcutdir=.", "--", "."]

BUGGY = r'[re.match(r"(\d+)([hm])", text).groups()]'
FIXED = r're.findall(r"(\d+)([hm])", text)'


def copy_fixture(tmp_path):
    dst = tmp_path / "timelog"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def run_pytest(cwd):
    return subprocess.run(PYTEST, cwd=cwd, capture_output=True, text=True, timeout=30)


def test_unfixed_project_has_exactly_one_failure(tmp_path):
    result = run_pytest(copy_fixture(tmp_path))
    assert result.returncode == 1, result.stdout
    assert "1 failed" in result.stdout
    assert "3.75 != 4.25" in result.stdout


def test_fixing_one_expression_passes_all(tmp_path):
    ws = copy_fixture(tmp_path)
    parser = ws / "timelog" / "parser.py"
    source = parser.read_text()
    assert source.count(BUGGY) == 1
    parser.write_text(source.replace(BUGGY, FIXED))

    result = run_pytest(ws)
    assert result.returncode == 0, result.stdout


def test_fixlab_does_not_collect_fixtures():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert "tests/fixtures/" not in result.stdout
    assert "test_fixture.py" in result.stdout
