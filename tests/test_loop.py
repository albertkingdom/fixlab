# agent 迴圈的單元測試：用寫好劇本的假模型驗證 agent-loop 規格，不需要真的 LLM。
# 這個檔案目前只涵蓋 3.5 的部分：任務文字、模型自己決定、步數上限、提示文字。
# 重試、截斷、連續失敗、trace 的情境留給 6.x。
import json
from types import SimpleNamespace as NS

import pytest

from fixlab.loop import SYSTEM_PROMPT, run_agent
from fixlab.tools import register_tools
from fixlab.workspace import ToolResult, Workspace

TASK = "The tests under tests/ fail. Find the cause and fix it."


def native(name, **args):
    """假的原生 tool call。真實 API 的參數是 JSON 字串。"""
    return NS(function=NS(name=name, arguments=json.dumps(args)))


class FakeClient:
    """依序回傳劇本裡的回覆，並記下每次請求收到的對話與工具清單。"""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []   # 每次請求當下的對話（複製一份，之後迴圈還會繼續加訊息）
        self.tools = []  # 每次請求的 tools 參數
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, model, messages, tools, **kw):
        self.sent.append(list(messages))
        self.tools.append(tools)
        content, tool_calls = self.replies.pop(0)
        msg = NS(content=content, tool_calls=tool_calls, model_extra={})
        return NS(choices=[NS(message=msg, finish_reason="stop")], usage=NS(prompt_tokens=10, completion_tokens=5))


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "rules.py").write_text("def grace_days():\n    return 2\n")
    w = Workspace(tmp_path)
    register_tools(w)  # 真的 read_file 與 list_files

    # 真的 edit_file 與 run_tests 要到 3.8、3.10 才有，這裡用假的，只驗證迴圈會照模型的決定執行。
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
