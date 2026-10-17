# tool call 解析的單元測試：對應 tool-call-parsing 規格，一個情境一個測試。
from dataclasses import dataclass

from fixlab.toolparse import parse_message

# 任務 3.x 有真正的工具定義後，改成引用它們。
SCHEMAS = {
    "read_file": {"required": ["path"]},
    "write_file": {"required": ["path", "content"]},
    "edit_file": {"required": ["path", "old_string", "new_string"]},
    "run_tests": {"required": []},
}


# 假的 API 回覆物件：欄位對應 OpenAI 格式的 message 與 message.tool_calls[i]。
# parse_message 只讀這幾個欄位，所以不需要真的 openai 類別。
@dataclass
class FakeFunction:
    name: str
    arguments: str  # 真實 API 的參數是 JSON 字串


@dataclass
class FakeToolCall:
    function: FakeFunction


@dataclass
class FakeMessage:
    content: str | None = None
    tool_calls: list[FakeToolCall] | None = None


def msg(content=None, tool_calls=None):
    return FakeMessage(content, tool_calls)


def tc(name, arguments):
    return FakeToolCall(FakeFunction(name, arguments))


# Requirement: Only native tool calls are parsed
def test_native_call_plus_json_in_text():
    r = parse_message(
        msg(content='{"name": "run_tests", "arguments": {}}', tool_calls=[tc("read_file", '{"path": "a.py"}')]),
        SCHEMAS,
    )
    assert [(c.name, c.arguments) for c in r.calls] == [("read_file", {"path": "a.py"})]
    assert r.errors == []


def test_json_only_in_text_is_not_a_call():
    r = parse_message(msg(content='{"name": "run_tests", "arguments": {}}'), SCHEMAS)
    assert r.calls == [] and r.errors == []


def test_two_native_calls_in_order():
    r = parse_message(msg(tool_calls=[tc("read_file", '{"path": "a.py"}'), tc("run_tests", "{}")]), SCHEMAS)
    assert [c.name for c in r.calls] == ["read_file", "run_tests"]
    assert r.errors == []


def test_native_bad_json_is_error_not_crash():
    r = parse_message(msg(tool_calls=[tc("read_file", '{"path": ')]), SCHEMAS)
    assert r.calls == [] and "bad arguments" in r.errors[0]


# 有些伺服器對沒有參數的工具送空字串，而不是 "{}"
def test_blank_arguments_mean_no_arguments():
    for blank in ["", "  ", "\n"]:
        r = parse_message(msg(tool_calls=[tc("run_tests", blank)]), SCHEMAS)
        assert [(c.name, c.arguments) for c in r.calls] == [("run_tests", {})], repr(blank)
        assert r.errors == []


def test_blank_arguments_still_fail_the_required_check():
    r = parse_message(msg(tool_calls=[tc("read_file", "")]), SCHEMAS)
    assert r.calls == [] and "missing required argument(s) ['path']" in r.errors[0]


def test_ordinary_text_is_not_a_call():
    r = parse_message(msg(content="Done. Example: {'a': 1}"), SCHEMAS)
    assert r.calls == [] and r.errors == []


# Requirement: Calls are validated against tool schemas
def test_missing_required_argument():
    r = parse_message(msg(tool_calls=[tc("edit_file", '{"path": "a.py", "old_string": "x"}')]), SCHEMAS)
    assert r.calls == [] and "missing" in r.errors[0]


def test_shell_tool_is_not_offered():
    r = parse_message(msg(tool_calls=[tc("bash", '{"command": "ls"}')]), SCHEMAS)
    assert r.calls == [] and "unknown tool: 'bash'" in r.errors[0]
