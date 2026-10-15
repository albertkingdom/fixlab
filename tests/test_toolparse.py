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


# Requirement: Native tool calls take precedence
def test_native_call_plus_json_in_text():
    r = parse_message(
        msg(content='{"name": "run_tests", "arguments": {}}', tool_calls=[tc("read_file", '{"path": "a.py"}')]),
        SCHEMAS,
    )
    assert [(c.name, c.arguments, c.source) for c in r.calls] == [("read_file", {"path": "a.py"}, "native")]
    assert r.errors == []


def test_native_bad_json_is_error_not_crash():
    r = parse_message(msg(tool_calls=[tc("read_file", '{"path": ')]), SCHEMAS)
    assert r.calls == [] and r.errors


# Requirement: Fallback parsing from reply text
def test_fallback_object_with_only_a_name():
    r = parse_message(msg(content='{"name": "run_tests"}'), SCHEMAS)
    assert [(c.name, c.arguments) for c in r.calls] == [("run_tests", {})]


def test_fallback_ordinary_json_with_name_field():
    r = parse_message(msg(content='Done. Example: {"name": "Alice", "age": 3}'), SCHEMAS)
    assert r.calls == [] and r.errors == ["unknown tool: 'Alice'"]


def test_fallback_two_calls_as_json_lines():
    content = (
        '{"name": "edit_file", "arguments": {"path": "a.py", "old_string": "x", "new_string": "y"}}\n'
        '{"name": "run_tests", "arguments": {}}'
    )
    r = parse_message(msg(content=content), SCHEMAS)
    assert [(c.name, c.source) for c in r.calls] == [("edit_file", "fallback"), ("run_tests", "fallback")]


# Requirement: Calls are validated against tool schemas
def test_missing_required_argument():
    r = parse_message(msg(tool_calls=[tc("edit_file", '{"path": "a.py", "old_string": "x"}')]), SCHEMAS)
    assert r.calls == [] and "missing" in r.errors[0]


def test_shell_tool_is_not_offered():
    r = parse_message(msg(tool_calls=[tc("bash", '{"command": "ls"}')]), SCHEMAS)
    assert r.calls == [] and "unknown tool: 'bash'" in r.errors[0]


# Requirement: Broken call attempts are errors, not silence
def test_python_triple_quotes_inside_json():
    content = '{"name": "edit_file", "arguments": {"path": "a.py", "old_string": "x", "new_string": """y"""}}'
    r = parse_message(msg(content=content), SCHEMAS)
    assert r.calls == [] and any("not valid JSON" in e for e in r.errors)


def test_ordinary_text_is_not_a_call():
    r = parse_message(msg(content="Done. Example: {'a': 1}"), SCHEMAS)
    assert r.calls == [] and r.errors == []
