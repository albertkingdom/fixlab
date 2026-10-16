"""七個工具的實作與登記入口。

各工具在自己的任務裡加進來。CLI 與測試都呼叫 register_tools()，所以工具清單只在這裡有一份。
每個工具都是一個函式：第一個參數是 Workspace（要用它檢查路徑），其餘是模型給的參數。
"""

from functools import partial

from fixlab.workspace import ToolError, ToolResult, Workspace

# 工具輸出一律有上限：輸出會留在對話歷史裡每一輪重送，是成本與小模型 context 的主要壓力。
MAX_READ_CHARS = 20000

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


def register_tools(ws: Workspace) -> None:
    """把所有工具登記到 ws。之後每個工具的任務各加一行 ws.register(...)。"""
    ws.register("read_file", partial(read_file, ws), READ_FILE_SCHEMA, READ_FILE_DESCRIPTION)
