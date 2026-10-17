"""七個工具的實作與登記入口。

各工具在自己的任務裡加進來。CLI 與測試都呼叫 register_tools()，所以工具清單只在這裡有一份。
每個工具都是一個函式：第一個參數是 Workspace（要用它檢查路徑），其餘是模型給的參數。
"""

from functools import partial

from fixlab.workspace import ToolError, ToolResult, Workspace, iter_files

# 工具輸出一律有上限：輸出會留在對話歷史裡每一輪重送，是成本與小模型 context 的主要壓力。
MAX_READ_CHARS = 20000
MAX_LIST_ENTRIES = 200

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


def read_file(ws: Workspace, path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult:
    p = ws.resolve_inside(path)
    if not p.exists():
        raise ToolError(f"file not found: {path!r}")
    if p.is_dir():
        raise ToolError(f"{path!r} is a directory, not a file; use list_files to see what it contains")
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
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
        ws.files_read.add(p)
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


def edit_file(ws: Workspace, path: str, old_string: str, new_string: str) -> ToolResult:
    p = ws.resolve_inside(path)
    if not p.exists():
        raise ToolError(f"file not found: {path!r}")
    if p.is_dir():
        raise ToolError(f"{path!r} is a directory, not a file")
    if old_string == "":
        # 空字串在任何檔案裡都「出現」，空檔還會剛好算成一次，等於把 new_string 塞進檔案。
        raise ToolError("old_string must not be empty")
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

    try:
        data = text.replace(old_string, new_string, 1).encode("utf-8")  # 先編碼再寫檔，編碼失敗時檔案不會被動到
    except UnicodeEncodeError:
        raise ToolError("new_string cannot be encoded as UTF-8") from None
    p.write_bytes(data)
    ws.files_read.discard(p)  # 模型沒看過編輯後的全文，之後要用 write_file 覆寫得重新讀
    return ToolResult(f"edited {path}", True)


def count_occurrences(text: str, piece: str) -> int:
    """piece 在 text 裡出現幾次，重疊的也算："aa" 在 "aaa" 裡是 2 次（str.count 只會回 1）。"""
    count = 0
    start = text.find(piece)
    while start != -1:
        count += 1
        start = text.find(piece, start + 1)  # 從下一個字元找起，重疊的位置才不會漏掉
    return count


def register_tools(ws: Workspace) -> None:
    """把所有工具登記到 ws。之後每個工具的任務各加一行 ws.register(...)。"""
    ws.register("read_file", partial(read_file, ws), READ_FILE_SCHEMA, READ_FILE_DESCRIPTION)
    ws.register("list_files", partial(list_files, ws), LIST_FILES_SCHEMA, LIST_FILES_DESCRIPTION)
    ws.register("edit_file", partial(edit_file, ws), EDIT_FILE_SCHEMA, EDIT_FILE_DESCRIPTION)
