"""互動模式的畫面：把一次工具呼叫、它的結果、與每個任務的結尾排成好讀的文字。

所有函式只回傳字串，不直接印；什麼時候印由 cli.py 決定，所以可以單獨測試格式。
顏色只在輸出是終端機、而且沒有設環境變數 NO_COLOR 時才開（NO_COLOR 是常見的慣例，見 no-color.org）。
"""

import os
import re
import sys

MAX_DIFF_LINES = 10   # 改檔的差異，每一段（刪掉的、加上的）最多顯示幾行
MAX_LINE_CHARS = 200  # 每一行最多顯示幾個字元
STYLES = {"green": "32", "red": "31", "dim": "2", "bold": "1"}  # ANSI 顏色碼


def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    return stream.isatty() and "NO_COLOR" not in os.environ


def paint(text: str, style: str) -> str:
    if not color_enabled():
        return text
    return f"\x1b[{STYLES[style]}m{text}\x1b[0m"


def call_header(name: str, args: dict) -> str:
    """一個工具呼叫的標題行：「  ▸ 工具 它要動什麼」。"""
    detail = call_detail(name, args)
    return f"  {paint('▸', 'bold')} {name}" + (f" {detail}" if detail else "")


def call_detail(name: str, args: dict) -> str:
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
    return ""


def edit_diff_lines(old: str, new: str) -> list[str]:
    """改檔要顯示的行：刪掉的以 - 開頭，加上的以 + 開頭。"""
    return changed_lines(old, "-", "red") + changed_lines(new, "+", "green")


def changed_lines(text: str, sign: str, color: str) -> list[str]:
    lines = text.splitlines()
    shown = [cut(line) for line in lines[:MAX_DIFF_LINES]]
    result = [paint(f"    {sign} {line}", color) for line in shown]
    if len(lines) > MAX_DIFF_LINES:
        result.append(f"    … {len(lines) - MAX_DIFF_LINES} more lines")
    return result


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
    """錯誤輸出的第一行，去掉開頭的 "error: "。"""
    first = output.splitlines()[0] if output else ""
    return first.removeprefix("error: ")


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
