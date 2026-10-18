"""fixlab 的入口，兩種模式，共用同一套檢查、工作目錄、工具與事件檔。

一次性（fixlab PATH）：檢查參數與金鑰 → 對 PATH 拍快照 → 跑 agent → 自己再跑一次測試 → 印結果與快照 diff。
最後那次測試不聽模型怎麼說，結果決定結束碼：0 是測試通過，1 是沒通過，2 是輸入有誤。
一次性執行沒有人在旁邊授權，所以改成事後審查，diff 涵蓋測試檔，竄改看得到。
互動（fixlab PATH -i）：一次讀一行當任務，同一個 session 內保留對話；使用者在場，不自動再跑測試。
agent 直接修改 PATH，不複製、不寫回，請對有備份或已 commit 的目錄使用。兩種模式的過程都寫進事件檔。
"""

import argparse
import difflib
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import openai
from openai import OpenAI

from fixlab.display import call_header, edit_diff_lines, footer_line, result_line
from fixlab.loop import DEFAULT_MAX_STEPS, run_agent
from fixlab.sandbox import sandbox_status
from fixlab.telemetry import EventLog, default_log_dir
from fixlab.tools import plan_edit, register_tools
from fixlab.workspace import FIXLAB_ROOT, ToolError, Workspace, iter_files, looks_like_test_file

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
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="read tasks from the keyboard and keep the conversation between them")
    parser.add_argument("--task", default=DEFAULT_TASK, help="replace the default task text (one-shot only)")
    parser.add_argument("--log-dir", help="where event logs go (default: ~/.fixlab/runs)")
    parser.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE",
                        help="record an experiment condition in the event log, e.g. quantization=Q4_K_M (repeatable)")
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
    try:
        meta = parse_meta(args.meta)
    except ValueError as error:
        return fail(str(error))
    log_dir = Path(args.log_dir).expanduser() if args.log_dir else default_log_dir()
    if is_inside(log_dir, root):
        # 事件檔放在被修的目錄裡，快照 diff 會把它當成新檔，模型與被測的程式也碰得到自己的紀錄
        return fail(f"the log directory {log_dir} is inside the target {root}; use --log-dir to put it elsewhere")
    print(f"editing in place: {root}", file=sys.stderr)
    print(f"sandbox: {sandbox_status()}", file=sys.stderr)  # 沙箱是安全功能，沒開要讓使用者看得到

    mode = "interactive" if args.interactive else "once"
    log = EventLog(log_dir, model)
    if log.path is not None:
        print(f"log: {log.path}", file=sys.stderr)
    log.write("run_start", **run_conditions(args, model, root, meta, mode))

    # 修 bug：測試檔是評分標準，模型不能改，被執行的程式也不能改。
    # 互動模式使用者在場，寫檔與跑測試前問一聲；一次性執行沒有人可以問，沿用預設（全部放行）。
    workspace_class = ShownWorkspace if args.interactive else Workspace
    options = {"confirm": make_asker()} if args.interactive else {}
    ws = workspace_class(root, read_only=looks_like_test_file, protect_tests=True, **options)
    register_tools(ws)
    try:
        if args.interactive:
            return run_interactive(client, model, ws, args, log)
        return run_once(client, model, ws, root, args, log)
    finally:
        log.close()


def run_once(client, model: str, ws: Workspace, root: Path, args, log: EventLog) -> int:
    """一次性：跑一個任務，結束後自己再跑一次測試，印結果與快照 diff。"""
    before = take_snapshot(root)
    log.write("task_start", task=1, text=args.task)
    result = run_agent(client, model, ws, args.task, max_steps=args.max_steps,
                       request_extra={"max_tokens": args.max_tokens}, trace=trace_to(log, 1, print_step))

    # 模型可能沒跑測試就宣告完成，所以結束後自己再跑一次，看真正的結果。
    # 先跑測試、再拍「之後」的快照：測試程式在跑的過程中動了什麼檔案，也會出現在差異裡。
    final = ws.call("run_tests", {})
    after = take_snapshot(root)

    log.write("task_end", task=1, **task_result_fields(result),
              final_tests={"tests_passed": final.flags.get("tests_passed", False),
                           "timed_out": final.flags.get("timed_out", False)},
              changed_files=changed_files(before, after))

    print(summary_line(result))
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


def run_interactive(client, model: str, ws: Workspace, args, log: EventLog) -> int:
    """互動：一次讀一行，每一行是一個任務；同一個 session 內的任務共用一份對話。"""
    session = []  # 這個 session 的對話；/reset 清空，結束就沒了，不存檔
    task_number = 0
    while True:
        try:
            line = input("fixlab> ").strip()
        except (EOFError, KeyboardInterrupt):  # Ctrl-D 或在提示字元上按 Ctrl-C：離開
            print()  # 提示字元後面沒有換行，補一個，shell 的提示字元才不會接在後面
            return 0
        if not line:
            continue
        if line == "/exit":
            return 0
        if line == "/reset":
            session.clear()
            print("conversation cleared")
            continue
        task_number += 1
        run_task(client, model, ws, args, log, session, task_number, line)


def run_task(client, model: str, ws: Workspace, args, log: EventLog, session: list, number: int, text: str) -> None:
    log.write("task_start", task=number, text=text)
    before = len(session)  # 任務開始前的對話長度；請求失敗時截回這裡
    started = time.perf_counter()
    print()  # 使用者打的那一行和第一個工具呼叫之間空一行
    try:
        result = run_agent(client, model, ws, text, messages=session, max_steps=args.max_steps,
                           request_extra={"max_tokens": args.max_tokens}, trace=trace_to(log, number, print_problem))
    except KeyboardInterrupt:
        # 已完成的部分留在對話裡（迴圈已把沒有結果的工具呼叫補上結果），再接一則說明：
        # 下一個任務的模型才知道前面做到哪裡、哪些檔案可能已經被改了。
        session.append({"role": "assistant", "content": INTERRUPT_NOTE})
        print()  # 按 Ctrl-C 時游標可能停在問題後面，換一行再印
        print("interrupted; what was done so far is kept (files may already have been changed; use /reset to start over)")
        log.write("task_end", task=number, stop_reason="interrupted", steps=None, counters=None, prompt_tokens=None,
                  completion_tokens=None, seconds=round(time.perf_counter() - started, 2),
                  final_tests=None, changed_files=None)
        return

    print()
    if result.stop_reason == "done":
        # 迴圈把模型最後的回覆放在對話最後面：那就是使用者要的答案。有些模型的回覆開頭帶空行，去掉，才不會空好幾行
        reply = session[-1]["content"].strip("\n")
        if reply:
            print(reply)
            print()
    print(footer_line(result))
    if result.stop_reason == "error":
        did_something = any(message["role"] in ("assistant", "tool") for message in session[before:])
        if not did_something:
            # 第一個請求就失敗：這個任務只多了（第一個任務還有 system prompt 與）一則沒有回覆的 user 訊息，
            # 下一個任務接上去會變成兩則連續的 user 訊息，有些模型的模板會直接拒絕。沒有做過任何事，丟掉就好。
            del session[before:]
            print("this task was discarded because the request failed")
        else:
            # 前面已經做了一些事（改過的檔案還在磁碟上）：和 Ctrl-C 一樣保留，接一則說明給下一個任務的模型看，
            # 不然它不知道檔案被改過。跑滿步數與卡住也是保留，對話仍然完整，使用者可以叫模型接著做。
            session.append({"role": "assistant", "content": REQUEST_FAILED_NOTE})
            print("the request failed; what was done so far is kept (files may already have been changed; use /reset to start over)")
    # 互動模式使用者在場，想驗證可以直接叫模型跑測試，所以沒有最後的測試結果與檔案變動
    log.write("task_end", task=number, **task_result_fields(result), final_tests=None, changed_files=None)


class ShownWorkspace(Workspace):
    """互動模式用的 Workspace：每個工具呼叫前後把畫面印出來（標題行、改檔的差異、結果行）。
    問題是在 call 裡面問的，所以標題要在 call 之前印、結果要在 call 之後印，順序才對。"""

    def call(self, name: str, args: dict):
        print(call_header(name, args))
        if name == "edit_file":
            for line in self.edit_preview(args):
                print(line)
        result = super().call(name, args)
        print(result_line(result))
        return result

    def edit_preview(self, args: dict) -> list[str]:
        """改檔會造成的差異：整個檔案改前與改後的比對。用執行時同一份驗證（plan_edit）；套不上的修改
        （參數不對、找不到字串、唯讀檔…）不顯示差異，結果行會說明原因。"""
        if set(args) != {"path", "old_string", "new_string"}:
            return []
        path, old, new = args["path"], args["old_string"], args["new_string"]
        if not all(isinstance(value, str) for value in (path, old, new)):
            return []
        try:
            _, before = plan_edit(self, path, old, new)
        except (ToolError, OSError):
            return []
        return edit_diff_lines(before, before.replace(old, new, 1))


# 會改檔或執行程式的工具才問；讀取類工具直接放行
ASKED_TOOLS = ("edit_file", "write_file", "run_tests")
INTERRUPT_NOTE = "[The user interrupted this task.]"  # 接在被打斷的任務後面，給下一個任務的模型看
REQUEST_FAILED_NOTE = "[The task stopped because the request failed.]"  # 同上，用在請求失敗、但前面已經做了一些事的任務


def make_asker():
    """回傳互動模式的確認函式 confirm(工具名稱, 參數) -> bool。「一律放行」的記錄放在這個函式自己的 always 裡，
    只在這個 session 內有效（/reset 不會清掉它），而且只對同一個工具。"""
    always = set()

    def ask(name: str, args: dict) -> bool:
        if name not in ASKED_TOOLS or name in always:
            return True
        try:
            answer = input("    Allow? [y]es / [a]lways for this tool / [N]o: ")
        except EOFError:  # 輸入結束了，沒有人可以同意：拒絕
            print()  # 問題後面沒有換行，補一個，下一行的結果才不會接在後面
            return False
        answer = answer.strip().lower()
        if answer in ("a", "always"):
            always.add(name)
            return True
        return answer in ("y", "yes")  # 其他一律拒絕，包括空白

    return ask


def summary_line(result) -> str:
    return (f"stop reason: {result.stop_reason}  steps: {result.steps}  "
            f"tokens: {result.prompt_tokens} prompt + {result.completion_tokens} completion")


def task_result_fields(result) -> dict:
    """task_end 事件裡兩種模式共有的欄位。"""
    return {"stop_reason": result.stop_reason, "steps": result.steps, "counters": result.counters,
            "prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens,
            "seconds": result.seconds}


def fail(message: str) -> int:
    print(f"fixlab: error: {message}", file=sys.stderr)
    return 2


def parse_meta(items: list[str]) -> dict[str, str]:
    """把 ["quantization=Q4_K_M", ...] 變成 {"quantization": "Q4_K_M"}。只切第一個等號，值裡面還可以有等號。"""
    meta = {}
    for item in items:
        key, equals, value = item.partition("=")
        if not equals or not key:
            raise ValueError(f"--meta needs KEY=VALUE, got {item!r}")
        meta[key] = value
    return meta


def is_inside(folder: Path, root: Path) -> bool:
    """folder 是不是 root 本身或在它底下。先解析成真實路徑，符號連結藏不住重疊。"""
    real = folder.resolve()
    return real == root or root in real.parents


def run_conditions(args, model: str, root: Path, meta: dict, mode: str) -> dict:
    """run_start 事件的內容：這次執行的條件。只放程式本來就知道的；量化方式之類 API 不會告訴我們的，之後由 --meta 補。"""
    return {
        "schema": 1, "mode": mode, "model": model, "base_url": os.environ.get("OPENAI_BASE_URL"),
        "path": str(root), "max_steps": args.max_steps, "max_tokens": args.max_tokens,
        "sandbox": sandbox_status(), "fixlab_commit": fixlab_commit(),
        "python": platform.python_version(), "openai": openai.__version__, "meta": meta,
    }


def fixlab_commit() -> str | None:
    """fixlab 自己程式的 git commit。fixlab 的資料夾必須自己就是 git 工作樹的最上層：不在 git 底下（例如用 pip 裝的）、
    或在別人的 repo 底下（例如裝進專案的 .venv），都是 None，不能把別人專案的 commit 記成 fixlab 的版本。"""
    try:
        done = subprocess.run(["git", "-C", str(FIXLAB_ROOT), "rev-parse", "--show-toplevel", "HEAD"],
                              capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = done.stdout.splitlines()
    if done.returncode != 0 or len(lines) < 2:
        return None
    top_level, commit = lines[0], lines[1]
    return commit.strip() if Path(top_level).resolve() == Path(FIXLAB_ROOT).resolve() else None


def trace_to(log: EventLog, task: int, printer):
    """trace 回呼：每筆紀錄交給 printer 決定要不要印，同時寫進事件檔。"""
    def trace(record: dict) -> None:
        printer(record)
        log.write("trace", task=task, record=record)
    return trace


def print_problem(record: dict) -> None:
    """互動模式的 trace 輸出：工具呼叫的畫面由 ShownWorkspace 印，這裡只印出問題。"""
    event = record.get("event")
    if event == "request_error":
        print(f"  ! request failed: {record['error']}")
    elif event == "retry":
        print(f"  ! the server is busy, retrying (attempt {record['attempt']})")
    elif event == "invalid_tool_call":
        print(f"  ! the model's tool call was invalid: {'; '.join(record['parse_errors'])}")


def print_step(record: dict) -> None:
    """trace 回呼：每個工具呼叫在 stderr 印一行。"""
    if record.get("event") == "request_error":
        print(f"request failed: {record['error']}", file=sys.stderr)
    for call in record.get("tool_calls", []):
        print(f"{call['name']}  ok={call['ok']}  flags={call['flags']}", file=sys.stderr)


def take_snapshot(root: Path) -> dict[str, bytes]:
    """記下 root 底下每個檔案的內容：{相對路徑: bytes}。跳過清單與符號連結的規則跟 list_files 一樣。"""
    # KNOWN-ISSUE: 每個檔案整個讀進記憶體；讀不了的檔案（例如沒有讀取權限）會讓入口丟出 PermissionError，印不出結果。
    snapshot = {}
    for path in iter_files(root):
        name = path.relative_to(root).as_posix()
        snapshot[name] = path.read_bytes()
    return snapshot


def changed_files(before: dict[str, bytes], after: dict[str, bytes]) -> dict[str, list[str]]:
    """哪些檔案新增、修改、刪除（路徑排序過）。事件檔用它，和印出的 diff 看的是同一份快照。"""
    added = sorted(name for name in after if name not in before)
    deleted = sorted(name for name in before if name not in after)
    modified = sorted(name for name in before if name in after and before[name] != after[name])
    return {"added": added, "modified": modified, "deleted": deleted}


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
