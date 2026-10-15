"""把模型回覆解析成工具呼叫（複製自 code-agent-eval 的 agent/toolparse.py）。

模型的工具呼叫有兩種寫法：API 的 tool_calls 欄位（原生），或寫在 content 文字裡的 JSON
（本機小模型常見）。parse_message 把兩種都轉成 ParsedCall，並擋掉不合法的。

四關流程，下面用同一個工具 read_file（必要參數 path）的幾則回覆說明：

  第 1 關 原生：tool_calls 非空就只用它，不看 content。
      tool_calls=[read_file, '{"path": "a.py"}']，content=""
      → calls=[read_file(path=a.py), source=native]，後面三關的文字處理全部略過。

  第 2 關 備援：沒有 tool_calls 才掃 content，有 "name" 的 JSON 物件就是候選。
      content='先看一下。{"name": "read_file", "arguments": {"path": "a.py"}}'
      → calls=[read_file(path=a.py), source=fallback]。
      content='{"name": "Alice", "age": 3}' 也會成為候選，要靠第 3 關淘汰。

  第 3 關 驗證：工具名稱不在清單、或缺必要參數，就從 calls 移到 errors。
      {"name": "bash", "arguments": {"cmd": "ls"}} → errors=["unknown tool: 'bash'"]
      {"name": "read_file", "arguments": {}}       → errors=["read_file: missing required argument(s) ['path']"]

  第 4 關 壞呼叫檢查（只在備援路徑）：calls 與 errors 都空，但文字像在呼叫工具，補一筆錯誤。
      content 的 JSON 裡 path 的值用了 Python 三引號（寫成 \"\"\"a.py\"\"\"），不是合法 JSON。
      第 2 關解析不出東西；若直接回傳空結果，loop 會以為模型說完了。
      → errors=["fallback: tool call in content is not valid JSON"]
      content='全部修好了。' 不像呼叫，保持空結果，loop 才能判定完成。

輸出（ParseResult）給 loop 的用法：
  calls 有、errors 空 → 執行；  calls 空、errors 空 → 模型說完了，結束；
  calls 空、errors 有 → 不結束，把錯誤回饋給模型；  兩者皆有 → 執行合法的並回報錯誤。
  所以結束判斷不能只看 calls 是否為空。

已知缺口（照原樣保留）：單引號 JSON {'name': 'x'} 取不到，也不會補錯誤。
"""

import json
import re
from dataclasses import dataclass, field


@dataclass
class ParsedCall:
    name: str
    arguments: dict
    source: str  # "native"（API 的 tool_calls 欄位）| "fallback"（從文字解析）


@dataclass
class ParseResult:
    calls: list[ParsedCall] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _iter_json_objects(text: str):
    """從任意文字中依序找出所有可以解析的 JSON 物件（略過解析失敗的部分）。

    例：'說明 {a, b}。{"name": "x", "arguments": {"p": 1}} 再 {"name": "y"}'
    - {a, b} 不是合法 JSON，解析失敗，往後一格繼續找。
    - 第二個 { 解析成功，連內層 {"p": 1} 一起取走，內層不會被當成獨立物件。
    - 從該物件結尾後繼續找，取得 {"name": "y"}。
    共 yield 兩個物件。
    """
    decoder = json.JSONDecoder()
    i = 0
    # := 一邊賦值一邊判斷：start 是下一個 { 的位置，找不到是 -1。括號不能省，否則 start 會變成 True/False。
    while (start := text.find("{", i)) != -1:
        try:
            # raw_decode 從 start 只解析一個完整 JSON，後面的文字不管；回傳（物件，結束位置）。
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            i = start + 1
            continue
        yield obj
        i = end


def _coerce_args(raw) -> dict:
    """參數可能是物件，也可能是 JSON 字串（OpenAI 格式就是字串），統一轉成 dict。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    raise ValueError(f"arguments is not an object: {raw!r:.200}")


def validate(call: ParsedCall, tool_schemas: dict[str, dict]) -> str | None:
    """檢查呼叫是否合法：工具存在、必要參數齊全。回傳錯誤訊息，合法則回傳 None。"""
    schema = tool_schemas.get(call.name)
    if schema is None:
        return f"unknown tool: {call.name!r}"
    missing = [p for p in schema.get("required", []) if p not in call.arguments]
    if missing:
        return f"{call.name}: missing required argument(s) {missing}"
    return None


def parse_message(message, tool_schemas: dict[str, dict]) -> ParseResult:
    """從 OpenAI 格式的回覆訊息中取出工具呼叫。tool_schemas：工具名稱 → 參數 schema。"""
    result = ParseResult()

    # 第 1 關：原生呼叫。參數是 JSON 字串，轉成 dict。
    for tc in message.tool_calls or []:
        try:
            args = _coerce_args(tc.function.arguments)
        except (ValueError, json.JSONDecodeError) as e:
            result.errors.append(f"native: bad arguments for {tc.function.name}: {e}")
            continue
        result.calls.append(ParsedCall(tc.function.name, args, "native"))

    # 第 3 關（原生路徑）：驗證後直接結束，不看文字。
    if message.tool_calls:  # 有原生呼叫就不看文字
        _check(result, tool_schemas)
        return result

    # 第 2 關：備援，從文字取 JSON。只要 JSON 物件有 name 就當候選；參數取 arguments，沒有就取 parameters，再沒有就是空的。
    # 副作用：一般文字裡的 {"name": "Alice"} 也會變成候選，接著被判定為「未知工具」。
    for obj in _iter_json_objects(message.content or ""):
        if not isinstance(obj, dict) or "name" not in obj:
            continue
        raw = obj.get("arguments", obj.get("parameters", {}))
        try:
            args = _coerce_args(raw)
        except (ValueError, json.JSONDecodeError) as e:
            result.errors.append(f"fallback: bad arguments for {obj['name']}: {e}")
            continue
        result.calls.append(ParsedCall(obj["name"], args, "fallback"))

    # 第 3 關：驗證工具名稱與必要參數，不合法的移到 errors。
    _check(result, tool_schemas)
    # 第 4 關：什麼都沒取到、文字卻像在呼叫工具，補一筆錯誤，避免被當成「完成」。
    if not result.calls and not result.errors and _looks_like_call_attempt(message.content or "", tool_schemas):
        # 例如 JSON 裡用了 Python 的三引號、或字串沒有結尾引號
        result.errors.append("fallback: tool call in content is not valid JSON")
    return result


def _looks_like_call_attempt(content: str, tool_schemas: dict[str, dict]) -> bool:
    """文字看起來是不是「想呼叫工具」：有 <tool_call> 標籤、出現已知工具名稱、或呼叫的形狀。"""
    if "<tool_call>" in content:
        return True
    names = "|".join(re.escape(n) for n in tool_schemas)
    if re.search(rf'"name"\s*:\s*"({names})"', content):
        return True
    # 模型編造的工具名稱也算，例如 llama3.1 會呼叫不存在的 write_to_file
    return re.search(r'"name"\s*:\s*"[^"]+"\s*,\s*"(arguments|parameters)"\s*:', content) is not None


def _check(result: ParseResult, tool_schemas: dict[str, dict]) -> None:
    """把不合法的呼叫移到 errors，只留下合法的。"""
    valid = []
    for call in result.calls:
        if err := validate(call, tool_schemas):
            result.errors.append(err)
        else:
            valid.append(call)
    result.calls = valid
