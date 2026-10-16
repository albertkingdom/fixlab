"""Agent 迴圈：由模型決定下一步要用哪個工具、什麼時候算完成。

每一步四件事：問模型（_ask_model）→ 解讀回覆（_interpret_reply）→ 沒有工具呼叫就結束，
回覆壞掉就把錯誤回饋給模型 → 執行工具並把結果加回對話（_run_tool_calls）。
agent 與 workflow 的差別在這裡：程式從不決定工具的順序，只設最大步數當保險。一步＝一次模型呼叫。
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from fixlab.toolparse import ParsedCall, parse_message
from fixlab.workspace import Workspace

# 送給模型的提示文字維持英文。不點名個別工具：有／無 run_tests 的實驗要求 prompt 一致、只差工具。
SYSTEM_PROMPT = """You are a coding agent. Your working directory is a multi-file Python project with pytest tests (read-only).
Find the cause of the failing behavior and fix it in the source code.
Call one tool at a time and look at its result before deciding the next step.
When you are confident the fix is correct, reply with a short final message WITHOUT any tool call."""

# 多檔探索比單檔多很多步。20 是初始值，沒有實測依據，階段 3 用 telemetry 的步數分佈校準。
DEFAULT_MAX_STEPS = 20

# 遇到限流（429）或伺服器暫時錯誤時，依序等這些秒數再重試。放在模組層，測試可以把它改成 0。
RETRY_DELAYS_S = (5, 15, 30, 60, 120, 180, 300, 300)


@dataclass
class AgentResult:
    stop_reason: str  # "done"（模型宣告完成）| "max_steps"（步數用完）| "error"（請求失敗）
    steps: int
    counters: dict = field(default_factory=dict)  # 各種事件的次數，例如 parse_errors、tests_passed
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


@dataclass
class Interpretation:
    """模型一次回覆的解讀結果。"""
    calls: list[ParsedCall]  # 這一步要執行的工具呼叫
    errors: list[str]        # 要記錄（以及在沒有合法呼叫時要回饋給模型）的錯誤
    truncated: bool = False  # 回覆被輸出長度上限截斷
    empty: bool = False      # 回覆既沒有文字也沒有工具呼叫


def run_agent(
    client, model: str, ws: Workspace, task: str, *,
    max_steps: int = DEFAULT_MAX_STEPS, request_extra: dict | None = None,
    trace: Callable[[dict], None] = lambda rec: None,
) -> AgentResult:
    """跑一個任務。task 就是第一則 user 訊息，迴圈不加任何自己的內容。"""
    tools, schemas = ws.tool_specs(), ws.schemas()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    res = AgentResult(stop_reason="max_steps", steps=0)
    c = res.counters
    t_start = time.perf_counter()

    for step in range(1, max_steps + 1):
        res.steps = step
        # 1. 問模型
        try:
            resp, latency = _ask_model(client, c, trace, step, model=model, messages=messages,
                                       tools=tools, **(request_extra or {}))
        except Exception as e:  # noqa: BLE001 — 請求失敗只結束這一次，不讓整個程式崩潰
            _count(c, "request_errors")
            trace({"step": step, "event": "request_error", "error": repr(e)})
            res.stop_reason = "error"
            break
        if resp.usage:
            res.prompt_tokens += resp.usage.prompt_tokens or 0
            res.completion_tokens += resp.usage.completion_tokens or 0

        # 2. 解讀回覆，並更新計數器（所有計數都在這裡，讀者不用到別處找）
        msg = resp.choices[0].message
        it = _interpret_reply(resp, schemas, (request_extra or {}).get("max_tokens"))
        _count(c, "parse_errors", len(it.errors))
        _count(c, "truncated_replies", int(it.truncated))
        _count(c, "empty_responses", int(it.empty))
        rec = _step_record(step, latency, resp, it)

        # 3. 沒有要執行的工具：回覆壞掉就回饋錯誤再給一次機會；否則就是模型宣告完成
        if not it.calls:
            if it.errors:
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user", "content": "Your tool call was invalid: "
                                 + "; ".join(it.errors) + ". Please call a tool with valid arguments."})
                trace({**rec, "event": "invalid_tool_call"})
                continue
            trace({**rec, "event": "done"})
            res.stop_reason = "done"
            break

        # 4. 執行工具，結果加回對話
        _run_tool_calls(ws, it, msg, messages, c, rec)
        trace({**rec, "event": "tool_calls"})

    res.seconds = round(time.perf_counter() - t_start, 2)
    return res


# ── 以下是主迴圈用到的輔助函式 ──────────────────────────────────────────────


def _ask_model(client, counters: dict, trace, step: int, **kwargs):
    """送出請求；遇到暫時性錯誤就等一下再試。回傳（回覆, 延遲秒數），延遲不含等待時間。

    只重試 429／5xx／連線錯誤：這些是供應商那邊忙，跟模型無關。
    逾時不重試：逾時通常代表模型在失控地一直生成，重試只會掩蓋問題、浪費時間。
    """
    import openai

    for attempt in range(len(RETRY_DELAYS_S) + 1):
        t0 = time.perf_counter()
        try:
            return client.chat.completions.create(**kwargs), time.perf_counter() - t0
        except (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError) as e:
            # APITimeoutError 是 APIConnectionError 的子類別，要特別排除
            if isinstance(e, openai.APITimeoutError) or attempt == len(RETRY_DELAYS_S):
                raise
            _count(counters, "rate_limit_retries")
            trace({"step": step, "event": "retry", "attempt": attempt + 1, "error": repr(e)[:300]})
            time.sleep(RETRY_DELAYS_S[attempt])
    raise AssertionError("unreachable")


def _interpret_reply(resp, schemas: dict, max_tokens: int | None) -> Interpretation:
    """把模型回覆轉成「要執行的工具呼叫＋錯誤」。不修改任何計數器。"""
    msg = resp.choices[0].message
    parsed = parse_message(msg, schemas)

    # 被截斷的回覆：工具呼叫的 JSON 尾巴通常不見了（例如少了 path），原本的錯誤訊息會誤導模型，
    # 所以丟掉這次的呼叫，直接告訴它真正的原因。
    truncated = resp.choices[0].finish_reason == "length" or bool(
        max_tokens and resp.usage and (resp.usage.completion_tokens or 0) >= max_tokens)
    if truncated:
        limit = f"{max_tokens}-token output limit" if max_tokens else "output limit"
        return Interpretation(calls=[], truncated=True, errors=[
            f"your reply was cut off at the {limit}, so the tool call was incomplete. "
            "Keep your reply and the tool arguments shorter."])

    # 空回覆不能算「宣告完成」：有些模型伺服器解析不了一個很長的工具呼叫時，會整個丟掉而不報錯。
    errors = list(parsed.errors)
    empty = not parsed.calls and not errors and not (msg.content or "").strip()
    if empty:
        errors.append("empty response (no text and no tool call)")
    return Interpretation(calls=parsed.calls, errors=errors, empty=empty)


def _step_record(step: int, latency: float, resp, it: Interpretation) -> dict:
    """這一步要寫進 trace 的紀錄（event 與 tool_calls 由主迴圈補上）。"""
    msg = resp.choices[0].message
    return {"step": step, "latency_s": round(latency, 2), "finish_reason": resp.choices[0].finish_reason,
            "provider": (getattr(resp, "model_extra", None) or {}).get("provider"),
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else None,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else None,
            "content": msg.content, "reasoning_chars": len((msg.model_extra or {}).get("reasoning") or ""),
            "parse_errors": it.errors, "tool_calls": []}


def _run_tool_calls(ws: Workspace, it: Interpretation, msg, messages: list, counters: dict, rec: dict) -> None:
    """執行工具、把結果加回對話、記錄旗標。"""
    # 先把這一輪的呼叫寫進對話歷史（assistant 訊息），每個呼叫配一個 id，結果再用同一個 id 接在後面。
    ids = [f"call_{uuid.uuid4().hex[:8]}" for _ in it.calls]
    messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
        {"id": i, "type": "function", "function": {"name": x.name, "arguments": json.dumps(x.arguments)}}
        for i, x in zip(ids, it.calls)]})
    for i, x in zip(ids, it.calls):
        result = ws.call(x.name, x.arguments)
        messages.append({"role": "tool", "tool_call_id": i, "content": result.output})
        for flag, val in result.flags.items():
            if val:  # 例如 tests_passed、blocked（被擋下）
                _count(counters, "blocked_calls" if flag == "blocked" else flag)
        rec["tool_calls"].append({"name": x.name,
                                  "args": {k: (v if len(str(v)) < 2000 else str(v)[:2000] + "...")
                                           for k, v in x.arguments.items()},
                                  "ok": result.ok, "flags": result.flags, "output": result.output[:2000]})


def _count(counters: dict, key: str, n: int = 1) -> None:
    """計數器加 n；n 為 0 時不建立這個欄位（輸出才不會充滿 0）。"""
    if n:
        counters[key] = counters.get(key, 0) + n
