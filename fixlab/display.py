"""互動模式的畫面：把一次工具呼叫、它的結果、與每個任務的結尾排成好讀的文字。

所有函式只回傳字串，不直接印；什麼時候印由 cli.py 決定，所以可以單獨測試格式。
顏色只在輸出是終端機、而且沒有設環境變數 NO_COLOR 時才開（NO_COLOR 是常見的慣例，見 no-color.org）。
"""

import difflib
import os
import re
import sys

CONTEXT_LINES = 3     # 改檔的差異，每處變動前後各帶幾行沒變的上下文
MAX_DIFF_LINES = 10   # 一處變動裡，連續刪掉的（或連續加上的）最多顯示幾行
MAX_DIFF_REGIONS = 8  # 一次改檔最多顯示幾處變動，其餘只說還有幾處
MAX_LINE_CHARS = 200  # 每一行最多顯示幾個字元
STYLES = {"green": "32", "red": "31", "dim": "2", "bold": "1"}  # ANSI 顏色碼


def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    return stream.isatty() and "NO_COLOR" not in os.environ


def paint(text: str, style: str) -> str:
    if not color_enabled():
        return text
    return f"\x1b[{STYLES[style]}m{text}\x1b[0m"


def call_header(name: str, args: dict, origin: tuple[str, str] | None = None) -> str:
    """一個工具呼叫的標題行：「  ▸ 工具 它要動什麼」。origin 是外部工具（MCP）的 (server, 原本的工具名稱)。"""
    detail = call_detail(name, args, origin)
    return f"  {paint('▸', 'bold')} {name}" + (f" {detail}" if detail else "")


def call_detail(name: str, args: dict, origin: tuple[str, str] | None = None) -> str:
    # 參數可能不合法（缺欄位、型別不對）：這裡用 get 取值，不能因為要顯示而出錯
    path = args.get("path", "")
    if name == "read_file":
        start, end = args.get("start_line"), args.get("end_line")
        if start is None and end is None:
            return path
        return f"{path} lines {start or 1}-{end if end is not None else 'end'}"
    if name == "list_files":
        return path or "."
    if name == "grep":
        where = f" in {path}" if path else ""
        return f"'{args.get('pattern', '')}'{where}"
    if name == "edit_file":
        return path
    if name == "write_file":
        return f"{path} ({len(str(args.get('content', '')))} characters)"
    if name == "run_tests":
        return args.get("target", ".")
    if origin is not None:
        # 外部工具：使用者要在同意前看得到它會做什麼，所以印出 server、原本的工具名稱與完整的參數
        server, tool = origin
        return f"(server {server}, tool {tool}) {mcp_arguments(args)}"
    return ""


def mcp_arguments(args: dict) -> str:
    """確認畫面上的參數：完整的 JSON，非 ASCII 字元一律跳脫。模型可以在參數裡放控制字元或改變文字方向的字元，
    讓畫面上看到的和實際送出的不一樣，所以不能原樣印。太長的參數不截斷，由詢問的地方直接拒絕（見 cli.make_asker）。"""
    import json
    return json.dumps(args, ensure_ascii=True)


def edit_diff_lines(before: str, after: str) -> list[str]:
    """改檔要顯示的行：整個檔案改前與改後的差異。每一處變動以「@@ line N」開頭（N 是這一處第一個顯示的行，
    行號都是改前的檔案），前後各帶 3 行沒變的上下文。沒變的行與刪掉的行帶行號，刪掉的有 -；加上的有 +，不帶行號。
    相近的變動共用上下文，算同一處。"""
    old_lines = before.splitlines()
    new_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    regions = list(matcher.get_grouped_opcodes(CONTEXT_LINES))
    width = len(str(len(old_lines)))  # 行號欄的寬度，讓每一行對齊

    result = []
    for region in regions[:MAX_DIFF_REGIONS]:
        first_shown = region[0][1] + 1
        result.append(paint(f"    @@ line {first_shown}", "dim"))
        for kind, old_start, old_end, new_start, new_end in region:
            if kind == "equal":
                for index in range(old_start, old_end):
                    result.append(paint(diff_line(index + 1, " ", old_lines[index], width), "dim"))
            else:
                result += run_of_lines(old_lines[old_start:old_end], old_start + 1, "-", "red", width)
                result += run_of_lines(new_lines[new_start:new_end], None, "+", "green", width)
    if len(regions) > MAX_DIFF_REGIONS:
        result.append(f"    … {len(regions) - MAX_DIFF_REGIONS} more changes")
    return result


def run_of_lines(lines: list[str], first_number: int | None, sign: str, color: str, width: int) -> list[str]:
    """連續刪掉（或加上）的行，最多顯示 MAX_DIFF_LINES 行，多的只說還有幾行。first_number 是第一行的行號，加上的行沒有。"""
    result = []
    for offset, line in enumerate(lines[:MAX_DIFF_LINES]):
        number = None if first_number is None else first_number + offset
        result.append(paint(diff_line(number, sign, line, width), color))
    if len(lines) > MAX_DIFF_LINES:
        result.append(f"    {' ' * width}   … {len(lines) - MAX_DIFF_LINES} more lines")
    return result


def diff_line(number: int | None, sign: str, text: str, width: int) -> str:
    label = str(number).rjust(width) if number is not None else " " * width
    return f"    {label} {sign} {cut(text)}".rstrip()


def cut(line: str) -> str:
    return line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] + "…"


def result_line(result) -> str:
    """一個工具呼叫的結果行：成功是 ✓，失敗是 ✗ 加上原因。result 是 ToolResult。"""
    flags = result.flags
    if flags.get("denied"):
        return "    " + paint("✗ declined", "red")
    if flags.get("blocked"):
        return "    " + paint(f"✗ blocked: {reason(result.output)}", "red")
    if not result.ok:
        return "    " + paint(f"✗ {reason(result.output)}", "red")
    if "tests_passed" in flags:
        return test_result_line(result)
    return "    " + paint("✓", "green")


def reason(output: str) -> str:
    """錯誤輸出的第一行，去掉開頭的 "error: "。不可列印的字元（跳脫序列、改變文字方向的字元）改成看得見的跳脫寫法：
    外部工具的錯誤可能回顯模型給的參數，原樣印出會讓模型控制終端機，遮住下一次的確認畫面。"""
    first = output.splitlines()[0] if output else ""
    return printable(first.removeprefix("error: "))


def printable(text: str) -> str:
    return "".join(c if c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in text)


def test_result_line(result) -> str:
    """run_tests 的結果：測試沒過不算工具失敗（ok 是 True），但對使用者來說是 ✗。"""
    if result.flags.get("timed_out"):
        return "    " + paint("✗ timed out", "red")
    summary = pytest_summary(result.output)
    if result.flags.get("tests_passed"):
        return "    " + paint(f"✓ {summary or 'tests passed'}", "green")
    return "    " + paint(f"✗ {summary or 'tests failed'}", "red")


def pytest_summary(output: str) -> str | None:
    """pytest 最後那一行摘要，例如 "1 failed, 4 passed in 0.01s"；找不到就是 None。"""
    for line in reversed(output.splitlines()):
        if re.match(r"^\d+ \w+.* in [\d.]+s", line):
            return line
    return None


def footer_line(result) -> str:
    """任務結束後的一行用量。result 是 AgentResult。"""
    steps = f"{result.steps} step" + ("" if result.steps == 1 else "s")
    parts = [steps, f"{result.prompt_tokens:,} + {result.completion_tokens:,} tokens", f"{result.seconds:.0f} s"]
    if result.stop_reason != "done":
        parts.insert(0, f"stopped: {result.stop_reason}")
    return paint("(" + " · ".join(parts) + ")", "dim")
