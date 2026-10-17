# 黃金 trace：把「假模型修好 timelog」整個過程的對外行為存下來，之後改動迴圈或工具時，任何行為變化都會被看到。
"""黃金 trace 測試：用固定的假模型劇本，在真的工具、真的 timelog 副本上跑完一次修復流程。

比對兩樣東西：
  (a) 假模型每次收到的完整對話與工具名稱清單，提示文字或工具輸出格式被改也會被抓到；
  (b) 每筆 trace 記錄去掉時間欄位後的全部內容，加上最終計數器、stop reason 與修好後的 parser.py。
預期值存在 tests/golden/trace_golden.json。需要重新產生時（只有在「刻意改變行為」的變更中）：
    UPDATE_GOLDEN=1 pytest tests/test_trace_golden.py
重新產生後要看 git diff，確認每一處變動都是你要的。

_normalize 的寫法沿用自己先前的評測實驗，去掉每次執行都會變的部分。
"""

import json
import os
import re
from pathlib import Path

import pytest

from fixlab.loop import run_agent
from fixlab.tools import register_tools
from fixlab.workspace import Workspace, looks_like_test_file
from test_fixture import BUGGY, FIXED, copy_fixture  # 把 timelog 複製到暫存目錄；bug 與修法
from test_loop import FakeClient, native  # 依序回傳劇本回覆的假 client

GOLDEN = Path(__file__).parent / "golden" / "trace_golden.json"
TASK = "The tests under tests/ fail. Find the cause and fix it."

# 一個涵蓋各種情況的劇本：每一項是一次模型呼叫。
SCRIPT = [
    (None, [native("list_files")]),                                                  # 看專案結構
    (None, [native("grep", pattern="parse_duration")]),                              # 找函式在哪裡被用到
    (None, [native("read_file", path="timelog/report.py"),                           # 同一個回覆讀兩個檔
            native("read_file", path="timelog/parser.py")]),
    (None, [native("run_tests")]),                                                   # 測試失敗（不算工具失敗）
    (None, [native("edit_file", path="tests/test_report.py",                         # 想改測試檔，被擋下
             old_string="3.75", new_string="4.25")]),
    (None, [native("edit_file", path="timelog/parser.py", old_string=BUGGY, new_string=FIXED)]),  # 真正的修法
    (None, [native("run_tests")]),                                                   # 測試通過
    ("Fixed parse_duration.", None),                                                 # 宣告完成
]


def _normalize(obj):
    """去掉每次執行都會變的部分：隨機的呼叫 id、pytest 耗時、暫存目錄路徑、時間欄位。"""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    text = re.sub(r"call_[0-9a-f]{8}", "call_ID", text)
    text = re.sub(r"in \d+\.\d+s", "in Xs", text)
    text = re.sub(r"/[^\"\s]*pytest-of-[^\"\s]*", "<TMP>", text)
    obj = json.loads(text)
    for record in obj["trace"]:
        record.pop("latency_s", None)
    return obj


def run_repair(tmp_path):
    root = copy_fixture(tmp_path)
    ws = Workspace(root, read_only=looks_like_test_file, protect_tests=True)  # 和 fixlab PATH 的設定相同
    register_tools(ws)
    client, trace = FakeClient(SCRIPT), []
    result = run_agent(client, "fake-model", ws, TASK, trace=trace.append)
    return _normalize({
        "requests": [{"messages": messages, "tools": [t["function"]["name"] for t in tools]}
                     for messages, tools in zip(client.sent, client.tools)],
        "trace": trace,
        "stop_reason": result.stop_reason,
        "steps": result.steps,
        "counters": result.counters,
        "tokens": [result.prompt_tokens, result.completion_tokens],
        "final_parser": (root / "timelog" / "parser.py").read_text(),
    })


# 規格：Every step is traced、All native calls in one reply are executed
def test_golden_trace(tmp_path):
    actual = run_repair(tmp_path)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(json.dumps(actual, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
        pytest.skip("golden file regenerated")
    assert actual == json.loads(GOLDEN.read_text())


def test_golden_covers_the_intended_cases():
    """確認劇本真的走到每一種情況，避免黃金檔案只記錄到一半就結束。"""
    golden = json.loads(GOLDEN.read_text())
    assert [r["event"] for r in golden["trace"]] == ["tool_calls"] * 7 + ["done"]
    assert golden["stop_reason"] == "done" and golden["steps"] == 8
    assert golden["counters"] == {"tests_passed": 1, "blocked_calls": 1}
    two_reads = golden["trace"][2]["tool_calls"]
    assert [c["name"] for c in two_reads] == ["read_file", "read_file"]  # 同一個回覆的兩個呼叫都有紀錄
    failed_run = golden["trace"][3]["tool_calls"][0]  # 測試失敗是旗標，不是工具失敗
    assert failed_run["ok"] is True and failed_run["flags"]["tests_passed"] is False
    assert golden["trace"][4]["tool_calls"][0]["flags"] == {"blocked": True}  # 改測試檔被擋
    assert FIXED in golden["final_parser"] and BUGGY not in golden["final_parser"]
