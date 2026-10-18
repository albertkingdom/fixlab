"""各工具的實作與登記入口。

各工具在自己的任務裡加進來。CLI 與測試都呼叫 register_tools()，所以工具清單只在這裡有一份。
每個工具都是一個函式：第一個參數是 Workspace（要用它檢查路徑），其餘是模型給的參數。
"""

import os
import re
import subprocess
import tempfile
import time
from functools import partial
from pathlib import Path

import regex

from fixlab.sandbox import sandbox_available, wrap_command
from fixlab.workspace import ToolError, ToolResult, Workspace, file_digest, iter_files

# 工具輸出一律有上限：輸出會留在對話歷史裡每一輪重送，是成本與小模型 context 的主要壓力。
MAX_READ_CHARS = 20000
MAX_LIST_ENTRIES = 200
MAX_TEST_OUTPUT_CHARS = 4000
MAX_GREP_LINES = 100
MAX_GREP_MATCH_CHARS = 2000  # 每行只比對前這麼多字元，壓縮過的超長一行不會拖垮比對
MAX_GREP_SHOWN_CHARS = 200   # 輸出時每行最多顯示這麼多字元；100 行長行會把上下文塞滿
GREP_LINE_TIMEOUT_S = 1      # 比對一行的時間上限，擋災難性回溯
GREP_TOTAL_TIMEOUT_S = 5     # 整個搜尋的時間上限。這幾個秒數做成模組常數，測試可以改短
RUN_TESTS_TIMEOUT_S = 10  # 做成模組常數，測試無窮迴圈的案例時可以改短，不用真的等 10 秒

# 啟動 pytest 的程式。不用 `python -m pytest`：-m 會把工作目錄放在模組搜尋路徑的最前面，
# 工作目錄裡的 pytest.py 或 _pytest/ 就會取代真的 pytest（被測的程式可以偽造「1 passed」）。
# 改成 -P（不自動加入工作目錄），先載入真的 pytest，再把工作目錄加到最後面，讓測試仍然找得到專案的模組。
# 已知缺口（code review，記在 design.md）：pytest 啟動後自動載入 plugin 時，工作目錄已經在搜尋路徑上，
# 根目錄放一個 trio.py 之類的檔案仍能騙過去；根治靠階段 3 的「用乾淨的環境重跑計分」，不靠在這裡一條條堵。
START_PYTEST = "import os, sys, pytest; sys.path.append(os.getcwd()); sys.exit(pytest.main(sys.argv[1:]))"

# 測試子行程從父行程繼承的環境變數。用白名單：金鑰的名字無法窮舉（OPENAI_KEY、STRIPE_SK、GH_PAT……），
# 而且被執行的程式包含模型改寫過的檔案，只要印出環境，金鑰就會進入測試輸出與對話。
# TMPDIR 不在這裡：每次執行都換成專屬的暫存目錄（見 run_tests）。
CHILD_ENV_NAMES = ("PATH", "LANG", "LC_ALL")

READ_FILE_DESCRIPTION = (
    "Read a text file in the working directory. Every line is prefixed with its line number. "
    "Use start_line and end_line (1-based, inclusive) to read only part of a long file. "
    f"Output longer than {MAX_READ_CHARS} characters is cut."
)
READ_FILE_SCHEMA = {
    "properties": {
        "path": {"type": "string"},
        "start_line": {"type": "integer"},
        "end_line": {"type": "integer"},
    },
    "required": ["path"],
}
LIST_FILES_DESCRIPTION = (
    "List the files under a directory (default: the working directory), recursively, "
    "one path per line, relative to the working directory. "
    "Skips .git, .venv, __pycache__, .pytest_cache and symbolic links. "
    f"At most {MAX_LIST_ENTRIES} entries are shown."
)
LIST_FILES_SCHEMA = {"properties": {"path": {"type": "string"}}, "required": []}
EDIT_FILE_DESCRIPTION = (
    "Replace one piece of text in an existing UTF-8 text file. "
    "old_string must match the file exactly (spaces, indentation, line breaks) and occur exactly once; "
    "if it is not unique, include more surrounding lines. "
    "Do not include the line numbers that read_file prints. new_string may be empty to delete the text."
)
EDIT_FILE_SCHEMA = {
    "properties": {
        "path": {"type": "string"},
        "old_string": {"type": "string"},
        "new_string": {"type": "string"},
    },
    "required": ["path", "old_string", "new_string"],
}
RUN_TESTS_DESCRIPTION = (
    "Run the project's pytest tests and return the output. "
    "target is an optional file or directory inside the working directory (default: the whole project). "
    f"Tests are stopped after {RUN_TESTS_TIMEOUT_S} seconds. "
    f"Output longer than {MAX_TEST_OUTPUT_CHARS} characters is shortened: the start and the end are kept."
)
RUN_TESTS_SCHEMA = {"properties": {"target": {"type": "string"}}, "required": []}
GREP_DESCRIPTION = (
    "Search file contents with a regular expression (Python syntax). "
    "Returns matching lines as path:line_number:text, sorted by path. "
    "path is an optional file or directory inside the working directory (default: the whole project). "
    "The search is case-sensitive; start the pattern with (?i) to ignore case. "
    "Skips .git, .venv, __pycache__, .pytest_cache, symbolic links and files that are not UTF-8 text. "
    f"At most {MAX_GREP_LINES} lines are shown, and each line is shortened to {MAX_GREP_SHOWN_CHARS} characters."
)
GREP_SCHEMA = {"properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}
WRITE_FILE_DESCRIPTION = (
    "Create a new file, or replace the whole content of an existing file. Missing parent directories are created. "
    "To change only part of a file, use edit_file instead. "
    "An existing file can only be replaced after you have read all of it with read_file "
    "(a partial or cut-off read does not count), and not if it changed since you read it."
)
WRITE_FILE_SCHEMA = {"properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}


def read_file(ws: Workspace, path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult:
    p = ws.resolve_inside(path)
    if not p.exists():
        raise ToolError(f"file not found: {path!r}")
    if p.is_dir():
        raise ToolError(f"{path!r} is a directory, not a file; use list_files to see what it contains")
    data = p.read_bytes()
    # KNOWN-ISSUE: splitlines 也會在 \x0c、\x1c-\x1e、\x85、\u2028 斷行，含這些字元的檔案，行號會和 Python 與 pytest 回溯的對不上
    # （grep 一樣）。改成只用 \n、\r\n 斷行即可，延後。
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        # 解碼失敗不是 OSError，不處理的話會一路拋出去，讓 loop 崩潰。
        raise ToolError(f"not a UTF-8 text file: {path!r}") from None

    if not lines:
        output = "(empty file)"
    else:
        first = 1 if start_line is None else start_line
        last = len(lines) if end_line is None else min(end_line, len(lines))
        if first < 1:
            raise ToolError("start_line must be at least 1")
        if end_line is not None and end_line < first:
            raise ToolError("end_line must not be smaller than start_line")
        if first > len(lines):
            raise ToolError(f"start_line {first} is past the end of the file ({len(lines)} lines)")
        # 6 位右對齊的行號加 tab：模型之後要用 start_line/end_line 或 edit_file 的上下文回頭找位置。
        output = "\n".join(f"{n:>6}\t{lines[n - 1]}" for n in range(first, last + 1))

    truncated = len(output) > MAX_READ_CHARS
    if truncated:
        # 截斷一定要明講，模型才知道自己沒看到全部。
        note = f"[truncated: {len(output)} characters in total, showing the first {MAX_READ_CHARS}; use start_line and end_line to read the rest]"
        output = output[:MAX_READ_CHARS] + "\n" + note

    # 只有沒帶行範圍、也沒被截斷的讀取，才算模型看過整個檔案。
    if start_line is None and end_line is None and not truncated:
        ws.files_read[p] = file_digest(data)  # 連同讀的當下的內容指紋一起記
    return ToolResult(output, True)


def list_files(ws: Workspace, path: str = ".") -> ToolResult:
    start = ws.resolve_inside(path)
    if not start.exists():
        raise ToolError(f"directory not found: {path!r}")
    if not start.is_dir():
        raise ToolError(f"{path!r} is not a directory; use read_file to read it")

    # 相對於工作目錄（不是 start），模型拿去呼叫 read_file 時才不用再拼路徑。
    names = sorted(p.relative_to(ws.root).as_posix() for p in iter_files(start))
    if not names:
        # 空結果要明確回報，模型才分得出「沒有檔案」與「呼叫失敗」。
        return ToolResult("no files listed", True)

    omitted = len(names) - MAX_LIST_ENTRIES
    if omitted > 0:
        names = names[:MAX_LIST_ENTRIES] + [f"[{omitted} more entries omitted; list a subdirectory to see them]"]
    return ToolResult("\n".join(names), True)


def plan_edit(ws: Workspace, path: str, old_string: str, new_string: str):
    """edit_file 的驗證：會讓它拒絕的情況都在這裡檢查，不動任何檔案。回傳（真實路徑, 檔案原本的文字）。
    edit_file 一開頭呼叫它；工作區也在問使用者之前先呼叫它（precheck），注定失敗的修改就不會拿去問。"""
    p = ws.resolve_writable(path)  # 路徑守門，加上測試檔保護；放在檢查檔案是否存在之前
    if not p.exists():
        raise ToolError(f"file not found: {path!r}")
    if p.is_dir():
        raise ToolError(f"{path!r} is a directory, not a file")
    if old_string == "":
        # 空字串沒有明確的位置：非空檔會算成「字元數加一」次而被拒絕，空檔卻剛好算成一次而成功，行為不一致。
        # 所以明確拒絕，並告訴模型插入文字的做法：拿檔案裡已有的一段文字當錨點。
        raise ToolError(
            "old_string must not be empty. To insert text, use a nearby line that already exists as "
            "old_string and repeat it in new_string together with the new text."
        )
    if old_string == new_string:
        # 這種「修改」什麼都沒改卻回成功，模型會以為已經修好。
        raise ToolError("old_string and new_string are identical, nothing to change")

    # 用 bytes 讀寫：文字模式會把 \r\n 悄悄換成 \n，整個檔案的換行字元都被改掉。
    try:
        text = p.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"not a UTF-8 text file: {path!r}") from None

    count = count_occurrences(text, old_string)
    if count == 0:
        raise ToolError(
            f"old_string occurs 0 times in {path!r}. It must match the file exactly, including spaces "
            "and indentation, and must not include line numbers. Use read_file to check the current text."
        )
    if count > 1:
        raise ToolError(
            f"old_string occurs {count} times in {path!r}, but it must occur exactly once. "
            "Include more surrounding lines to make it unique."
        )
    return p, text


def edit_file(ws: Workspace, path: str, old_string: str, new_string: str) -> ToolResult:
    p, text = plan_edit(ws, path, old_string, new_string)
    try:
        data = text.replace(old_string, new_string, 1).encode("utf-8")  # 先編碼再寫檔，編碼失敗時檔案不會被動到
    except UnicodeEncodeError:
        raise ToolError("new_string cannot be encoded as UTF-8") from None
    p.write_bytes(data)
    ws.files_read.pop(p, None)  # 模型沒看過編輯後的全文，之後要用 write_file 覆寫得重新讀
    return ToolResult(f"edited {path}", True)


def grep(ws: Workspace, pattern: str, path: str = ".") -> ToolResult:
    if pattern == "":
        raise ToolError("pattern must not be empty")
    try:
        matcher = regex.compile(pattern)
    except regex.error as e:
        raise ToolError(f"invalid regular expression: {e}") from None

    start = ws.resolve_inside(path)
    if not start.exists():
        raise ToolError(f"path not found: {path!r}")

    # 單一檔案就搜它；資料夾就走訪，順序依完整相對路徑的字串，輸出才可預測。
    files = {}
    if start.is_file():
        files[start.relative_to(ws.root).as_posix()] = start
    else:
        for file in iter_files(start):
            files[file.relative_to(ws.root).as_posix()] = file

    deadline = time.monotonic() + GREP_TOTAL_TIMEOUT_S
    shown = []
    total = 0  # 符合的行數，包含超過上限而不顯示的
    stopped = False
    for name in sorted(files):
        # KNOWN-ISSUE: 整個檔案先讀進記憶體再切行，超大的文字檔會佔很多記憶體，5 秒的上限在讀檔期間不會生效。
        try:
            text = files[name].read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # 不是文字檔，或讀不了：略過
        for number, line in enumerate(text.splitlines(), start=1):
            try:
                found = matcher.search(line[:MAX_GREP_MATCH_CHARS], timeout=GREP_LINE_TIMEOUT_S)
            except TimeoutError:
                raise ToolError(
                    f"pattern too slow: matching one line took more than {GREP_LINE_TIMEOUT_S}s "
                    f"({name}:{number}). Use a simpler pattern."
                ) from None
            if found:
                total += 1
                if len(shown) < MAX_GREP_LINES:
                    shown.append(f"{name}:{number}:{shorten(line)}")
            if time.monotonic() > deadline:
                stopped = True
                break
        if stopped:
            break

    lines = list(shown)
    if total > len(shown):
        lines.append(f"[{total - len(shown)} more matches omitted; use a more specific pattern or path]")
    if stopped:
        lines.append(f"[search stopped after {GREP_TOTAL_TIMEOUT_S}s; the results above may be incomplete]")
    if not lines:
        # 空結果明確回報，模型才分得出「沒找到」與「呼叫失敗」。
        return ToolResult("no matches", True)
    return ToolResult("\n".join(lines), True)


def shorten(line: str) -> str:
    if len(line) <= MAX_GREP_SHOWN_CHARS:
        return line
    return line[:MAX_GREP_SHOWN_CHARS] + "..."


def count_occurrences(text: str, piece: str) -> int:
    """piece 在 text 裡出現幾次，重疊的也算："aa" 在 "aaa" 裡是 2 次（str.count 只會回 1）。"""
    count = 0
    start = text.find(piece)
    while start != -1:
        count += 1
        start = text.find(piece, start + 1)  # 從下一個字元找起，重疊的位置才不會漏掉
    return count


def plan_write(ws: Workspace, path: str, content: str):
    """write_file 的驗證：會讓它拒絕的情況都在這裡檢查，不動任何檔案。回傳（真實路徑, 要寫入的 bytes）。
    write_file 一開頭呼叫它；工作區也在問使用者之前先呼叫它（precheck）。"""
    p = ws.resolve_writable(path)  # 路徑守門，加上唯讀檢查；放在檢查檔案是否存在之前，不存在的測試檔路徑也擋
    try:
        data = content.encode("utf-8")  # 先編碼，失敗時還沒動任何東西
    except UnicodeEncodeError:
        raise ToolError("content cannot be encoded as UTF-8") from None

    if p.exists():
        if p.is_dir():
            raise ToolError(f"{path!r} is a directory, not a file")
        check_overwrite_allowed(ws, p, path)
    return p, data


def write_file(ws: Workspace, path: str, content: str) -> ToolResult:
    p, data = plan_write(ws, path, content)
    if p.exists():
        action = "overwrote"
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        action = "created"

    p.write_bytes(data)
    ws.files_read[p] = file_digest(data)  # 模型知道自己剛寫了什麼，之後不用再讀就能再覆寫
    return ToolResult(f"{action} {path} ({len(content)} characters)", True)


def check_overwrite_allowed(ws: Workspace, p, path: str) -> None:
    """覆寫既有檔案前：模型必須整檔讀過它，而且讀過之後內容沒有變。不行就丟 ToolError。"""
    recorded = ws.files_read.get(p)
    if recorded is None:
        raise ToolError(
            f"{path!r} already exists. You must read the file first with read_file "
            "(the whole file; a partial or cut-off read does not count) before overwriting it."
        )
    if file_digest(p.read_bytes()) != recorded:
        del ws.files_read[p]  # 記錄已經過期，留著沒有意義
        raise ToolError(
            f"{path!r} has changed since you read it. You must read the file first again before overwriting it."
        )


def plan_tests(ws: Workspace, target: str = ".") -> str:
    """run_tests 的驗證：目標先過路徑守門（跑出工作目錄 → blocked）。回傳相對於工作目錄的路徑。
    run_tests 一開頭呼叫它；工作區也在問使用者之前先呼叫它（precheck）。"""
    return ws.resolve_inside(target).relative_to(ws.root).as_posix()


def run_tests(ws: Workspace, target: str = ".") -> ToolResult:
    relative_target = plan_tests(ws, target)  # 用相對於工作目錄的路徑交給 pytest
    if relative_target != ".":
        # 加 ./ 前綴，讓 --version 這樣的名字變成路徑。實測 pytest 9.1.1 連 `-- --version` 都會先攔下來當選項，
        # 印出版本後以 0 結束，會被誤判成測試通過。
        relative_target = "./" + relative_target
    # 指令固定：-c /dev/null、--rootdir、--confcutdir 讓 pytest 不往上層目錄找設定與 conftest；
    # -p no:cacheprovider 不在工作目錄留下 .pytest_cache；-- 與目標的 ./ 前綴一起，確保目標只會被當成路徑。
    command = [ws.python, "-P", "-c", START_PYTEST, "-q", "-p", "no:cacheprovider",
               "-c", "/dev/null", "--rootdir=.", "--confcutdir=.", "--", relative_target]
    # 每次執行用專屬的暫存目錄：很多程式與測試（pytest 的 tmp_path）需要暫存檔，沙箱又不准寫工作目錄以外的地方。
    # 沒有它，pytest 會把暫存檔悄悄寫進工作目錄，弄髒結束時的差異比較。跑完整個刪掉。
    with tempfile.TemporaryDirectory(prefix="fixlab-run-") as tmp:
        tmpdir = Path(tmp).resolve()
        if sandbox_available():
            command = wrap_command(command, ws.root, ws.python, ws.project_root, ws.deny_read, tmpdir, ws.protect_tests)
        # KNOWN-ISSUE: 逾時只殺最上層的 pytest，測試啟動的子行程會變孤兒繼續跑（沙箱限制它能做什麼，但不會讓它停）。
        # 解法是 Popen 加 start_new_session=True，逾時後 os.killpg 整個行程群組。
        try:
            done = subprocess.run(command, cwd=ws.root, env=child_environment(tmpdir), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=RUN_TESTS_TIMEOUT_S)
            output, timed_out = done.stdout, False
            passed = done.returncode == 0 and has_a_passed_summary(done.stdout.decode("utf-8", errors="replace"))
        except subprocess.TimeoutExpired as e:
            output, timed_out, passed = e.stdout or b"", True, False
    text = output.decode("utf-8", errors="replace")
    if timed_out:
        text += f"\n[tests timed out after {RUN_TESTS_TIMEOUT_S}s]"
    # 測試失敗不是工具錯誤：失敗的測試正是模型需要的資訊，所以一律回成功，結果放在旗標裡。
    return ToolResult(clip_middle(text), True, {"tests_passed": passed, "timed_out": timed_out})


# KNOWN-ISSUE: 被測的程式可以自己印一行假的摘要，再讓結束碼是 0（例如在 atexit 裡印出後 os._exit(0)），tests_passed 就是 True。
# 2026-10-17 重現。根治在階段 3：計分用乾淨的環境重跑並比對測試案例清單；改讀 junitxml 沒用，被測的程式也能偽造那個檔。
def has_a_passed_summary(text: str) -> bool:
    """輸出裡要有一行 pytest 的摘要，例如 "5 passed in 0.01s" 或 "5 passed, 1 warning in 0.01s"。

    只看結束碼 0 不夠：被測的程式可以在 pytest 開始前用 os._exit(0) 結束，什麼都沒跑。
    不限定是最後一行：專案可能在結束時多印東西（atexit），測試明明通過卻被判失敗。
    這擋的是意外與簡單的偽造；程式自己印一行假的摘要擋不住（見 design.md）。"""
    return re.search(r"^\d+ passed\b.* in [\d.]+s\b", text, re.MULTILINE) is not None


def child_environment(tmpdir: Path) -> dict:
    """測試子行程的環境變數：白名單裡有設的、這次執行專屬的暫存目錄，再加上不產生 .pyc 的設定。"""
    env = {}
    for name in CHILD_ENV_NAMES:
        if name in os.environ:
            env[name] = os.environ[name]
    env["TMPDIR"] = str(tmpdir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def clip_middle(text: str, limit: int = MAX_TEST_OUTPUT_CHARS) -> str:
    """太長就留頭尾各一半、中間註明省略。pytest 最重要的資訊（失敗摘要與最後一行 1 failed）在尾端，只留開頭會看不到結果。"""
    if len(text) <= limit:
        return text
    half = limit // 2
    note = f"[truncated: {len(text)} characters in total, showing the first {half} and the last {half}]"
    return text[:half] + "\n" + note + "\n" + text[-half:]


def register_tools(ws: Workspace) -> None:
    """把所有工具登記到 ws。之後每個工具的任務各加一行 ws.register(...)。"""
    ws.register("read_file", partial(read_file, ws), READ_FILE_SCHEMA, READ_FILE_DESCRIPTION)
    ws.register("list_files", partial(list_files, ws), LIST_FILES_SCHEMA, LIST_FILES_DESCRIPTION)
    ws.register("edit_file", partial(edit_file, ws), EDIT_FILE_SCHEMA, EDIT_FILE_DESCRIPTION, partial(plan_edit, ws))
    ws.register("grep", partial(grep, ws), GREP_SCHEMA, GREP_DESCRIPTION)
    ws.register("write_file", partial(write_file, ws), WRITE_FILE_SCHEMA, WRITE_FILE_DESCRIPTION, partial(plan_write, ws))
    ws.register("run_tests", partial(run_tests, ws), RUN_TESTS_SCHEMA, RUN_TESTS_DESCRIPTION, partial(plan_tests, ws))
