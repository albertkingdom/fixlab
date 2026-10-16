"""把模型回覆解析成工具呼叫。

只看 API 的 tool_calls 欄位（原生）。沒有原生呼叫的回覆就是純文字，文字裡就算有 JSON 也不理會，
loop 會把這種回覆當成模型說完了。不支援把工具呼叫寫在文字裡的模型（原因見 design 的
「只解析原生 tool_calls，不做文字備援解析」）。

兩關流程，下面用同一個工具 read_file（必要參數 path）的幾則回覆說明：

  第 1 關 解碼：每個原生呼叫的參數是 JSON 字串，轉成 dict；轉不成就記一筆錯誤。
      tool_calls=[read_file, '{"path": "a.py"}']  → calls=[read_file(path=a.py)]
      tool_calls=[read_file, '{"path": ']          → errors=["bad arguments for read_file: ..."]
      tool_calls=None，content='{"name": "read_file", ...}' → 什麼都沒有（文字不看）。

  第 2 關 驗證：工具名稱不在清單、或缺必要參數，就從 calls 移到 errors。
      {"name": "bash", "arguments": {"cmd": "ls"}} → errors=["unknown tool: 'bash'"]
      read_file 的參數是空的                        → errors=["read_file: missing required argument(s) ['path']"]

輸出（ParseResult）給 loop 的用法：
  calls 有 → 執行（errors 有就一併回報）；  calls 空、errors 有 → 不結束，把錯誤回饋給模型；
  兩者皆空 → 模型說完了，結束。
"""

import json
from dataclasses import dataclass, field


@dataclass
class ParsedCall:
    name: str
    arguments: dict


@dataclass
class ParseResult:
    calls: list[ParsedCall] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _coerce_args(raw) -> dict:
    """參數是 JSON 字串（OpenAI 格式），轉成 dict；不是物件就 raise ValueError。"""
    if isinstance(raw, str):
        value = json.loads(raw)  # JSONDecodeError 是 ValueError 的子類別
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

    # 第 1 關：解碼參數。沒有 tool_calls 時這裡什麼都不做，回覆文字完全不看。
    for tc in message.tool_calls or []:
        try:
            args = _coerce_args(tc.function.arguments)
        except ValueError as e:
            result.errors.append(f"bad arguments for {tc.function.name}: {e}")
            continue
        result.calls.append(ParsedCall(tc.function.name, args))

    # 第 2 關：驗證工具名稱與必要參數，不合法的移到 errors。
    valid = []
    for call in result.calls:
        if err := validate(call, tool_schemas):
            result.errors.append(err)
        else:
            valid.append(call)
    result.calls = valid
    return result
