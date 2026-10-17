# agent 迴圈的單元測試：用寫好劇本的假模型驗證 agent-loop 規格，不需要真的 LLM。
# 這個檔案涵蓋任務文字、模型自己決定、步數上限、提示文字、回覆異常、同一回覆的多個呼叫、重試、trace、連續失敗保險。
import json
from types import SimpleNamespace as NS

import openai
import pytest

# openai 3.x 改用 httpx2 發請求，舊版用 httpx；測試要自己造 openai 的例外，需要同一套 Request 與 Response。
try:
    import httpx2 as httpx
except ImportError:
    import httpx

from fixlab.loop import SYSTEM_PROMPT, run_agent
from fixlab.tools import register_tools
from fixlab.workspace import ToolResult, Workspace, looks_like_test_file

TASK = "The tests under tests/ fail. Find the cause and fix it."


def native(name, **args):
    """假的原生 tool call。真實 API 的參數是 JSON 字串。"""
    return NS(function=NS(name=name, arguments=json.dumps(args)))


class FakeClient:
    """依序回傳劇本裡的回覆，並記下每次請求收到的對話與工具清單。

    劇本的每一項是 (文字, 工具呼叫) 或 (文字, 工具呼叫, finish_reason)；如果是例外物件，這次請求就丟出它。
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []   # 每次請求當下的對話（複製一份，之後迴圈還會繼續加訊息）
        self.tools = []  # 每次請求的 tools 參數
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, model, messages, tools, **kw):
        self.sent.append(list(messages))
        self.tools.append(tools)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        content, tool_calls = reply[0], reply[1]
        finish_reason = reply[2] if len(reply) == 3 else "stop"
        msg = NS(content=content, tool_calls=tool_calls, model_extra={})
        return NS(choices=[NS(message=msg, finish_reason=finish_reason)],
                  usage=NS(prompt_tokens=10, completion_tokens=5))


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "rules.py").write_text("def grace_days():\n    return 2\n")
    w = Workspace(tmp_path)
    register_tools(w)  # 真的 read_file 與 list_files

    # edit_file 與 run_tests 在這裡用假的：只驗證迴圈會照模型的決定執行，不依賴真工具的細節。
    def edit_file(path: str, old_string: str, new_string: str) -> ToolResult:
        p = w.resolve_inside(path)
        p.write_text(p.read_text().replace(old_string, new_string))
        return ToolResult("edited", True)

    def run_tests() -> ToolResult:
        passed = "return 3" in (tmp_path / "rules.py").read_text()
        return ToolResult("1 passed" if passed else "1 failed", True, {"tests_passed": passed})

    string3 = {"properties": {k: {"type": "string"} for k in ("path", "old_string", "new_string")},
               "required": ["path", "old_string", "new_string"]}
    w.register("edit_file", edit_file, string3, description="Replace one string in a file.")
    w.register("run_tests", run_tests, {"properties": {}, "required": []}, description="Run pytest.")
    return w


# Requirement: Task text is the first user message
def test_task_text_is_first_user_message(ws):
    client = FakeClient([("Done.", None)])
    run_agent(client, "m", ws, TASK)
    assert client.sent[0] == [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": TASK}]
    assert client.tools[0] == ws.tool_specs()  # 模型收到的工具清單就是登記表產生的那一份


# Requirement: Model decides the next step and when to stop
def test_read_edit_test_then_finish(ws):
    client = FakeClient([
        (None, [native("read_file", path="rules.py")]),
        (None, [native("edit_file", path="rules.py", old_string="return 2", new_string="return 3")]),
        (None, [native("run_tests")]),
        ("Fixed.", None),
    ])
    r = run_agent(client, "m", ws, TASK)
    assert r.stop_reason == "done" and r.steps == 4
    assert (ws.root / "rules.py").read_text() == "def grace_days():\n    return 3\n"
    # 第四次請求的對話裡有 run_tests 的結果：模型是看過測試結果才決定結束的
    assert any(m["role"] == "tool" and m["content"] == "1 passed" for m in client.sent[3])
    assert r.counters["tests_passed"] == 1


# Requirement: Step budget is a safety net
def test_max_steps_stops_a_model_that_never_finishes(ws):
    client = FakeClient([(None, [native("run_tests")])] * 5)
    r = run_agent(client, "m", ws, TASK, max_steps=3)
    assert r.stop_reason == "max_steps" and r.steps == 3
    assert len(client.sent) == 3


def test_default_budget_is_20_steps(ws):
    client = FakeClient([(None, [native("list_files")])] * 25)
    r = run_agent(client, "m", ws, TASK)
    assert r.stop_reason == "max_steps" and r.steps == 20
    assert len(client.sent) == 20


def test_system_prompt_is_the_same_for_every_tool_set():
    # 有／無 run_tests 的實驗只能差工具，所以提示文字不能點名工具，也不能提到範例題目的檔案。
    tool_names = ["read_file", "list_files", "glob", "grep", "edit_file", "write_file", "run_tests"]
    assert "solution.py" not in SYSTEM_PROMPT
    assert not [n for n in tool_names if n in SYSTEM_PROMPT]


# Scenario: Empty reply
def test_empty_reply_is_not_completion_and_the_model_may_just_finish(ws):
    client = FakeClient([(None, None), ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and r.steps == 2
    assert r.counters["empty_responses"] == 1 and r.counters["parse_errors"] == 1
    feedback = client.sent[1][-1]  # 第二次請求的最後一則訊息，就是回饋
    assert feedback["role"] == "user"
    assert "reply was empty" in feedback["content"] and "final message" in feedback["content"]


# Scenario: Missing required argument
def test_missing_required_argument_is_feedback_not_a_crash(ws):
    client = FakeClient([(None, [native("edit_file", path="rules.py")]), ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and r.steps == 2
    assert (ws.root / "rules.py").read_text() == "def grace_days():\n    return 2\n"  # 沒有改任何檔案
    assert "invalid" in client.sent[1][-1]["content"]
    assert r.counters["parse_errors"] == 1


# Scenario: Truncated reply
def test_a_truncated_reply_discards_its_tool_call(ws):
    cut_off = (None, [native("edit_file", path="rules.py", old_string="return 2", new_string="return 3")], "length")
    client = FakeClient([cut_off, ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and r.steps == 2
    assert (ws.root / "rules.py").read_text() == "def grace_days():\n    return 2\n"  # 被截斷的呼叫沒有執行
    assert "cut off" in client.sent[1][-1]["content"]
    assert r.counters["truncated_replies"] == 1


# ---- All native calls in one reply are executed ----

# Scenario: Two reads in one reply
def test_two_reads_in_one_reply_run_in_order_and_cost_one_step(ws):
    (ws.root / "other.py").write_text("OTHER = 1\n")
    two_reads = (None, [native("read_file", path="rules.py"), native("read_file", path="other.py")])
    client = FakeClient([two_reads, ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    # 兩次讀取加上一個「Done.」只用了兩步：同一個回覆裡的呼叫合起來算一步
    assert r.stop_reason == "done" and r.steps == 2
    asked = client.sent[1][-3:]  # 第二次請求的最後三則：assistant 的呼叫，加上兩個工具結果
    assert [m["role"] for m in asked] == ["assistant", "tool", "tool"]
    assert "grace_days" in asked[1]["content"] and "OTHER = 1" in asked[2]["content"]
    # 每個結果都用自己呼叫的 id 接在後面
    assert [m["tool_call_id"] for m in asked[1:]] == [c["id"] for c in asked[0]["tool_calls"]]


# 規格沒有寫「同一個回覆裡有合法也有不合法的呼叫」：合法的照常執行，不合法的要告訴模型沒有執行
def test_an_invalid_call_next_to_a_valid_one_is_reported_to_the_model(ws):
    mixed = (None, [native("read_file", path="rules.py"), native("edit_file", path="rules.py")])  # 第二個缺參數
    client = FakeClient([mixed, ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and r.counters["parse_errors"] == 1
    tail = client.sent[1][-3:]  # assistant 的呼叫、合法呼叫的結果、關於不合法呼叫的通知
    assert [m["role"] for m in tail] == ["assistant", "tool", "user"]
    assert "grace_days" in tail[1]["content"]  # 合法的那個有執行
    assert "not run" in tail[2]["content"] and "missing required" in tail[2]["content"]


def test_the_notice_about_an_invalid_call_does_not_hide_a_failing_round(ws):
    # 合法的呼叫失敗、不合法的呼叫被丟掉：這一輪仍然算全部失敗
    mixed = (None, [native("read_file", path="nope.py"), native("edit_file", path="rules.py")])
    client = FakeClient([mixed] * 4)
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "stuck" and r.steps == 3


# ---- Transient provider errors are retried, timeouts are not ----

@pytest.fixture
def no_wait(monkeypatch):
    """重試之間不真的等。"""
    monkeypatch.setattr("fixlab.loop.RETRY_DELAYS_S", (0, 0))


def provider_error(kind):
    request = httpx.Request("POST", "http://localhost/v1/chat/completions")
    if kind == "429":
        return openai.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    if kind == "500":
        return openai.InternalServerError("oops", response=httpx.Response(500, request=request), body=None)
    if kind == "connection":
        return openai.APIConnectionError(request=request)
    return openai.APITimeoutError(request=request)


# Scenario: One rate limit then success
@pytest.mark.parametrize("kind", ["429", "500", "connection"])
def test_a_transient_error_is_retried(ws, no_wait, kind):
    client = FakeClient([provider_error(kind), ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done"
    assert r.counters["rate_limit_retries"] == 1 and "request_errors" not in r.counters


# Scenario: Timeout is not retried
def test_a_timeout_is_not_retried(ws, no_wait):
    client = FakeClient([provider_error("timeout"), ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "error"
    assert r.counters["request_errors"] == 1 and "rate_limit_retries" not in r.counters
    assert len(client.replies) == 1  # 第二個回覆沒有被用到


def test_a_request_that_keeps_failing_ends_the_run_without_raising(ws, no_wait):
    client = FakeClient([provider_error("429")] * 3)  # 第一次請求加上兩次重試，全部失敗
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "error"
    assert r.counters["rate_limit_retries"] == 2 and r.counters["request_errors"] == 1


# ---- Every step is traced ----

# Scenario: Trace for a tool step
def test_each_answered_model_call_gets_one_trace_record(ws):
    records = []
    client = FakeClient([(None, [native("read_file", path="rules.py")]), ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    assert [r["event"] for r in records] == ["tool_calls", "done"]
    first, last = records
    assert first["step"] == 1 and first["finish_reason"] == "stop"
    assert first["prompt_tokens"] == 10 and first["completion_tokens"] == 5
    assert first["content"] is None and first["parse_errors"] == []
    assert first["latency_s"] >= 0
    assert first["tool_calls"] == [{
        "name": "read_file", "args": {"path": "rules.py"}, "ok": True, "flags": {},
        "output": "     1\tdef grace_days():\n     2\t    return 2"}]
    assert last["step"] == 2 and last["content"] == "Done." and last["tool_calls"] == []


def test_an_invalid_reply_is_traced_with_its_parse_errors(ws):
    records = []
    client = FakeClient([(None, [native("edit_file", path="rules.py")]), ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    assert [r["event"] for r in records] == ["invalid_tool_call", "done"]
    assert records[0]["parse_errors"] and records[0]["tool_calls"] == []


def test_a_tool_step_records_every_call_of_the_reply_and_its_flags(ws):
    records = []
    two_calls = (None, [native("run_tests"), native("read_file", path="nope.py")])
    client = FakeClient([two_calls, ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    run_tests_entry, read_entry = records[0]["tool_calls"]
    assert run_tests_entry["name"] == "run_tests" and run_tests_entry["flags"] == {"tests_passed": False}
    assert read_entry["name"] == "read_file" and read_entry["ok"] is False


# Scenario: Long arguments and outputs are truncated
def test_arguments_and_outputs_over_2000_characters_are_truncated_in_the_record(ws):
    records = []
    (ws.root / "big.py").write_text("x = 1\n" * 1000)  # 讀回來的輸出遠超過 2000 字元
    long_edit = native("edit_file", path="rules.py", old_string="return 2", new_string="return 3" + "#" * 3000)
    client = FakeClient([(None, [native("read_file", path="big.py"), long_edit]), ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    read_entry, edit_entry = records[0]["tool_calls"]
    assert len(read_entry["output"]) == 2000
    assert edit_entry["args"]["new_string"] == ("return 3" + "#" * 3000)[:2000] + "..."
    assert edit_entry["args"]["old_string"] == "return 2"  # 短的參數不動
    # 截斷只影響紀錄：工具真的收到完整的字串
    assert (ws.root / "rules.py").read_text() == "def grace_days():\n    return 3" + "#" * 3000 + "\n"


def test_an_argument_of_exactly_2000_characters_is_kept_whole(ws):
    records = []
    exactly = "x" * 2000
    client = FakeClient([(None, [native("edit_file", path="rules.py", old_string="return 2", new_string=exactly)]),
                         ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    assert records[0]["tool_calls"][0]["args"]["new_string"] == exactly


# ---- Step records show truncation and the original call count ----

# Scenario: Cut-off reply
def test_a_cut_off_reply_is_marked_truncated_in_its_record(ws):
    records = []
    cut_off = (None, [native("edit_file", path="rules.py", old_string="return 2", new_string="return 3")], "length")
    client = FakeClient([cut_off, ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    assert records[0]["truncated"] is True and records[0]["reply_tool_calls"] == 1
    assert records[0]["tool_calls"] == []  # 被截斷的呼叫沒有執行
    assert (ws.root / "rules.py").read_text() == "def grace_days():\n    return 2\n"


# Scenario: One valid and one invalid call
def test_the_record_counts_invalid_calls_too(ws):
    records = []
    mixed = (None, [native("read_file", path="rules.py"), native("edit_file", path="rules.py")])  # 第二個缺參數
    client = FakeClient([mixed, ("Done.", None)])
    run_agent(client, "m", ws, TASK, trace=records.append)

    assert records[0]["reply_tool_calls"] == 2 and records[0]["truncated"] is False
    assert len(records[0]["tool_calls"]) == 1 and len(records[0]["parse_errors"]) == 1


# Scenario: Reply without tools
def test_a_reply_without_tools_has_zero_calls(ws):
    records = []
    run_agent(FakeClient([("Done.", None)]), "m", ws, TASK, trace=records.append)

    assert records[0]["reply_tool_calls"] == 0 and records[0]["truncated"] is False


# ---- 連續失敗保險：對應規格的 Consecutive failing rounds stop the loop ----

def missing_file():
    return native("read_file", path="nope.py")


def a_listing():
    return native("list_files")


# Scenario: Three failing rounds in a row
def test_three_failing_rounds_in_a_row_stop_the_loop(ws):
    client = FakeClient([(None, [missing_file()])] * 4)
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "stuck" and r.steps == 3
    assert r.counters["stuck_failures"] == 3
    assert len(client.replies) == 1  # 第四個回覆沒有被用到


# Scenario: A success resets the counter
def test_a_success_resets_the_counter(ws):
    client = FakeClient([(None, [missing_file()]), (None, [a_listing()]), (None, [missing_file()]),
                         (None, [missing_file()]), ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and "stuck_failures" not in r.counters


# Scenario: Mixed round counts as success
def test_a_round_with_one_success_counts_as_a_success(ws):
    client = FakeClient([(None, [missing_file()]), (None, [missing_file()]),
                         (None, [missing_file(), a_listing()]),  # 一個失敗、一個成功：歸零
                         (None, [missing_file()]), ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and "stuck_failures" not in r.counters


def test_two_failing_calls_in_one_round_count_once(ws):
    client = FakeClient([(None, [missing_file(), missing_file()]), (None, [missing_file(), missing_file()]),
                         ("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and "stuck_failures" not in r.counters


# Scenario: Invalid reply between failures
def test_an_invalid_reply_neither_resets_nor_increments(ws):
    invalid = (None, [native("edit_file", path="rules.py")])  # 缺少必要的參數
    client = FakeClient([(None, [missing_file()]), invalid, (None, [missing_file()]),
                         (None, [missing_file()]), ("never used", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "stuck" and r.steps == 4
    assert r.counters["parse_errors"] == 1 and r.counters["stuck_failures"] == 3


# Scenario: Blocked calls count as failures
def test_blocked_calls_count_as_failures(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_report.py").write_text("def test_a():\n    assert True\n")
    w = Workspace(tmp_path, read_only=looks_like_test_file)
    register_tools(w)
    blocked = native("write_file", path="tests/test_report.py", content="x")
    client = FakeClient([(None, [blocked])] * 4)

    r = run_agent(client, "m", w, TASK)

    assert r.stop_reason == "stuck" and r.steps == 3
    assert r.counters["blocked_calls"] == 3


# 寫入唯讀檔案的嘗試也要在計數器裡看得到（事件檔的 task_end 帶計數器）
def test_protected_writes_are_counted_next_to_blocked_calls(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_report.py").write_text("def test_a():\n    assert True\n")
    w = Workspace(tmp_path, read_only=looks_like_test_file)
    register_tools(w)
    client = FakeClient([(None, [native("write_file", path="tests/test_report.py", content="x")]), ("Done.", None)])

    r = run_agent(client, "m", w, TASK)

    assert r.counters["blocked_calls"] == 1 and r.counters["protected_write_calls"] == 1


# Scenario: Failing tests are not tool failures
def test_failing_tests_are_not_tool_failures(ws):
    client = FakeClient([(None, [native("run_tests")])] * 3 + [("Done.", None)])
    r = run_agent(client, "m", ws, TASK)

    assert r.stop_reason == "done" and r.steps == 4
    assert "stuck_failures" not in r.counters
