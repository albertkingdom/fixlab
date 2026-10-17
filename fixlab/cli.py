"""fixlab 的最小入口（smoke 用，不是階段 2 的正式 CLI）。

流程：檢查參數與金鑰 → 對 PATH 拍快照 → 跑 agent → 自己再跑一次測試 → 印結果與快照 diff。
最後那次測試不聽模型怎麼說，結果決定結束碼：0 是測試通過，1 是沒通過，2 是輸入有誤。
agent 直接修改 PATH，不複製、不寫回；一次性執行沒有人在旁邊授權，所以改成事後審查，
diff 涵蓋測試檔，竄改看得到。因為直接改 PATH，請對有備份或已 commit 的目錄使用。
"""

import argparse
import difflib
import os
import sys
from pathlib import Path

from openai import OpenAI

from fixlab.loop import DEFAULT_MAX_STEPS, run_agent
from fixlab.tools import register_tools
from fixlab.sandbox import sandbox_status
from fixlab.workspace import Workspace, iter_files, looks_like_test_file

# 送給模型的任務文字維持英文。
DEFAULT_TASK = "The tests fail under pytest. Find the cause and fix it."
DEFAULT_MAX_TOKENS = 8192


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fixlab", description="Let the agent fix the failing tests in PATH. PATH is edited in place.")
    parser.add_argument("path")
    parser.add_argument("--model", help="model name (default: $FIXLAB_MODEL)")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--task", default=DEFAULT_TASK, help="replace the default task text")
    return parser


def main(argv=None, client=None) -> int:
    """argv 沒傳就讀終端機的參數；client 沒傳才建真的，傳了就直接用（只給測試注入假的）。"""
    args = build_parser().parse_args(argv)

    if not Path(args.path).is_dir():
        return fail(f"not a directory: {args.path}")
    model = args.model or os.environ.get("FIXLAB_MODEL")
    if not model:
        return fail("no model: pass --model or set FIXLAB_MODEL")
    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            return fail("OPENAI_API_KEY is not set (any placeholder value works for Ollama)")
        # 端點由環境變數 OPENAI_BASE_URL 指定，SDK 自己會讀。max_retries=0：重試由 loop 自己管。
        client = OpenAI(timeout=600, max_retries=0)

    root = Path(args.path).resolve()
    print(f"editing in place: {root}", file=sys.stderr)
    print(f"sandbox: {sandbox_status()}", file=sys.stderr)  # 沙箱是安全功能，沒開要讓使用者看得到
    before = take_snapshot(root)

    # 修 bug：測試檔是評分標準，模型不能改，被執行的程式也不能改
    ws = Workspace(root, read_only=looks_like_test_file, protect_tests=True)
    register_tools(ws)
    result = run_agent(client, model, ws, args.task, max_steps=args.max_steps,
                       request_extra={"max_tokens": args.max_tokens}, trace=print_step)

    # 模型可能沒跑測試就宣告完成，所以結束後自己再跑一次，看真正的結果。
    # 先跑測試、再拍「之後」的快照：測試程式在跑的過程中動了什麼檔案，也會出現在差異裡。
    final = ws.call("run_tests", {})
    after = take_snapshot(root)

    print(f"stop reason: {result.stop_reason}  steps: {result.steps}  "
          f"tokens: {result.prompt_tokens} prompt + {result.completion_tokens} completion")
    print("\nchanges since start:")
    print(diff_report(before, after))
    print("\nfinal test run:")
    print(final.output)

    passed = final.flags.get("tests_passed", False)
    if passed:
        print("RESULT: tests passed")  # 結論放在最後一行，一眼就看得到
    elif final.flags.get("timed_out"):
        print("RESULT: tests FAILED (timed out)")
    else:
        print("RESULT: tests FAILED")
    return 0 if passed else 1


def fail(message: str) -> int:
    print(f"fixlab: error: {message}", file=sys.stderr)
    return 2


def print_step(record: dict) -> None:
    """trace 回呼：每個工具呼叫在 stderr 印一行。"""
    if record.get("event") == "request_error":
        print(f"request failed: {record['error']}", file=sys.stderr)
    for call in record.get("tool_calls", []):
        print(f"{call['name']}  ok={call['ok']}  flags={call['flags']}", file=sys.stderr)


def take_snapshot(root: Path) -> dict[str, bytes]:
    """記下 root 底下每個檔案的內容：{相對路徑: bytes}。跳過清單與符號連結的規則跟 list_files 一樣。"""
    snapshot = {}
    for path in iter_files(root):
        name = path.relative_to(root).as_posix()
        snapshot[name] = path.read_bytes()
    return snapshot


def diff_report(before: dict[str, bytes], after: dict[str, bytes]) -> str:
    """比較兩份快照，回傳新增、刪除、修改的檔案的說明；完全沒變就回 "no changes"。"""
    parts = []
    for name in sorted(set(before) | set(after)):  # 兩邊檔名的聯集
        old, new = before.get(name), after.get(name)  # 新增的檔 old 是 None，刪除的檔 new 是 None
        if old != new:
            parts.append(describe_change(name, old, new))
    return "\n".join(parts) if parts else "no changes"


def describe_change(name: str, old: bytes | None, new: bytes | None) -> str:
    try:
        old_lines = to_lines(old)
        new_lines = to_lines(new)
    except UnicodeDecodeError:
        return f"binary file changed: {name}"

    diff = "\n".join(difflib.unified_diff(old_lines, new_lines, f"a/{name}", f"b/{name}", lineterm=""))
    if old is None:
        return f"new file: {name}\n{diff}"
    if new is None:
        return f"deleted file: {name}\n{diff}"
    # splitlines 看不出換行字元與結尾換行的差別，內容有變但 diff 是空的就明講。
    return diff or f"{name}: only line endings or the final newline changed"


def to_lines(data: bytes | None) -> list[str]:
    if data is None:
        return []
    return data.decode("utf-8").splitlines()
