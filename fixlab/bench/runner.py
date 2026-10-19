"""實驗執行器：展開（題目、模型、條件、第幾次），逐次執行 fixlab、評分、把結果一行一行寫進 results.jsonl。

每次執行：
  1. 把題目的 project 複製到暫存目錄（每次都是原始的，執行之間互不影響）。
  2. 以一次性模式呼叫 fixlab 的 main（原樣呼叫，不改它的介面），每次用自己的紀錄資料夾。
  3. 從那份事件檔取結果：task_end 有 stop_reason、步數、token、耗時，request_error 的 trace 有錯誤描述。
  4. 用評分器對暫存目錄評分，寫一行結果，刪掉暫存目錄（事件檔留著）。

每個模型自己的端點與金鑰：這次執行期間暫時設 OPENAI_BASE_URL 與 OPENAI_API_KEY，執行完還原，
所以 run_start 記到的 base_url 是對的。每次執行都會花錢，所以沒有確認選項只印計畫。
"""

import contextlib
import io
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fixlab import cli
from fixlab.bench.grader import grade
from fixlab.bench.problems import Problem, make_workdir, problem_digest

CONDITIONS = ("with_tests", "no_tests")
HIDDEN_TOOL = "run_tests"  # no_tests 條件隱藏的工具
RESERVED_META = ("problem", "condition", "repeat", "problem_digest")  # 執行器自己記的 meta，模型設定不能用這些名字


class ConfigError(ValueError):
    """模型設定檔或選項不對。"""


@dataclass
class ModelConfig:
    name: str            # 送給 API 的模型名稱
    label: str           # 結果與報告裡用的短名字
    base_url: str | None
    api_key_env: str     # 放金鑰的環境變數名稱（設定檔不放金鑰本身）
    temperature: float | None = None
    extra_body: dict | None = None
    price: dict | None = None   # input_per_million、output_per_million、source、date
    meta: dict = field(default_factory=dict)  # 量化方式、runtime、context 長度…，原樣記進 run_start 的 meta


@dataclass(frozen=True)
class RunSpec:
    problem: str
    model: str       # 模型的 label
    condition: str
    repeat: int      # 從 1 開始

    @property
    def key(self) -> tuple:
        return (self.problem, self.model, self.condition, self.repeat)


def load_models(path) -> list[ModelConfig]:
    """讀模型設定檔（JSON：一個清單，或 {"models": 清單}）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data["models"] if isinstance(data, dict) else data
    models = []
    for entry in entries:
        for key in ("name", "label", "api_key_env"):
            if key not in entry:
                raise ConfigError(f"model entry lacks the key {key!r}: {entry}")
        if not isinstance(entry.get("meta", {}), dict):
            raise ConfigError(f"model {entry['label']!r}: meta must be a JSON object")
        reserved = [key for key in entry.get("meta", {}) if key in RESERVED_META]
        if reserved:
            raise ConfigError(f"model {entry['label']!r}: meta must not use the reserved keys {', '.join(reserved)}")
        models.append(ModelConfig(
            name=entry["name"], label=entry["label"], base_url=entry.get("base_url"),
            api_key_env=entry["api_key_env"], temperature=entry.get("temperature"),
            extra_body=entry.get("extra_body"), price=entry.get("price"), meta=entry.get("meta", {})))
    return models


def plan_runs(problem_ids, models, conditions, repeats) -> list[RunSpec]:
    """展開成清單。次數放在最外層：同一輪先把每個題目、模型、條件都跑一遍，
    供應商一天內的變化才會平均分到各個條件，不會集中在其中一個。"""
    if repeats < 1:
        raise ConfigError(f"repeats must be at least 1, got {repeats}")
    return [RunSpec(problem, model.label, condition, repeat)
            for repeat in range(1, repeats + 1)
            for problem in problem_ids
            for model in models
            for condition in conditions]


def fixlab_arguments(workdir, model: ModelConfig, spec: RunSpec, digest: str, log_dir) -> list:
    """這一次執行傳給 fixlab 的命令列。兩個條件只差 condition 這個 meta 的值與 no_tests 多的 --hide-tool。"""
    arguments = [str(workdir), "--model", model.name, "--log-dir", str(log_dir)]
    meta = {"problem": spec.problem, "condition": spec.condition, "repeat": spec.repeat, "problem_digest": digest}
    meta.update(model.meta)
    for key, value in meta.items():
        arguments += ["--meta", f"{key}={value}"]
    if model.temperature is not None:
        arguments += ["--temperature", str(model.temperature)]
    if model.extra_body is not None:
        arguments += ["--extra-body", json.dumps(model.extra_body)]
    if spec.condition == "no_tests":
        arguments += ["--hide-tool", HIDDEN_TOOL]
    return arguments


@contextlib.contextmanager
def model_environment(model: ModelConfig):
    """這次執行期間暫時設端點與金鑰，結束後還原（包括原本沒設的）。
    模型沒寫 base_url 就把 OPENAI_BASE_URL 拿掉（用 SDK 的預設端點），不沿用呼叫者環境裡的：不然這個模型的金鑰會送去別人的端點。"""
    changes = {"OPENAI_API_KEY": os.environ[model.api_key_env], "OPENAI_BASE_URL": model.base_url or None}
    saved = {name: os.environ.get(name) for name in changes}
    for name, value in changes.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def read_events(log_dir: Path) -> tuple:
    """這次執行專屬資料夾裡的事件檔：回傳（路徑, 事件清單）；沒有就是（None, [])。"""
    paths = sorted(Path(log_dir).glob("*/events.jsonl"))
    if not paths:
        return None, []
    lines = paths[-1].read_text(encoding="utf-8").splitlines()
    return paths[-1], [json.loads(line) for line in lines if line.strip()]


def count_hidden_tool_calls(events: list, hidden: list) -> int:
    """trace 的解析錯誤裡提到被隱藏工具名稱的次數：模型在看不到的工具上亂叫的次數。"""
    count = 0
    for event in events:
        if event.get("event") != "trace":
            continue
        for message in event["record"].get("parse_errors", []):
            if any(name in message for name in hidden):
                count += 1
    return count


def run_one(spec: RunSpec, problem: Problem, model: ModelConfig, out_dir: Path, client=None) -> dict:
    """執行一次，回傳要寫進 results.jsonl 的一行。client 只給測試注入假的。"""
    digest = problem_digest(problem)
    log_dir = out_dir / "logs" / f"{spec.problem}-{spec.model}-{spec.condition}-{spec.repeat}"
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    workdir = make_workdir(problem)
    error = None
    try:
        arguments = fixlab_arguments(workdir, model, spec, digest, log_dir)
        try:
            with model_environment(model), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main(arguments, client=client)
        except Exception as exception:  # noqa: BLE001 — 一次失敗不能讓整個實驗中斷
            error = f"{type(exception).__name__}: {exception}"
        log_path, events = read_events(log_dir)
        task_end = next((event for event in events if event["event"] == "task_end"), None)
        if task_end is None:
            stop_reason = "error"
            error = error or "no task_end in the event log"
            steps = prompt_tokens = completion_tokens = seconds = None
        else:
            stop_reason = task_end["stop_reason"]
            steps, seconds = task_end["steps"], task_end["seconds"]
            prompt_tokens, completion_tokens = task_end["prompt_tokens"], task_end["completion_tokens"]
            if stop_reason == "error":
                failures = [e["record"]["error"] for e in events if e["event"] == "trace" and e["record"].get("event") == "request_error"]
                error = failures[-1] if failures else "request failed"
        graded = grade(problem, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    hidden = [HIDDEN_TOOL] if spec.condition == "no_tests" else []
    return {
        "problem": spec.problem, "problem_digest": digest, "model": spec.model, "condition": spec.condition,
        "repeat": spec.repeat, "grade": graded, "stop_reason": stop_reason, "steps": steps,
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "seconds": seconds,
        "claimed_done_but_failed": stop_reason == "done" and not graded["fixed"],
        "hidden_tool_calls": count_hidden_tool_calls(events, hidden),
        "log_path": str(log_path) if log_path else None, "started_at": started_at, "error": error,
    }


def read_results(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_by_key(lines: list) -> dict:
    """同一個組合有多行時（有錯誤的重跑過），只留最後一行。"""
    latest = {}
    for line in lines:
        latest[(line["problem"], line["model"], line["condition"], line["repeat"])] = line
    return latest


def pending_runs(plan: list, results_path) -> list:
    """還要跑的：沒有結果行、或最後一行有錯誤的組合。"""
    latest = latest_by_key(read_results(results_path))
    return [spec for spec in plan if spec.key not in latest or latest[spec.key]["error"] is not None]


def run_experiment(problems: dict, models: list, plan: list, out_dir, client_factory=None, progress=print) -> int:
    """依序執行還沒完成的組合，每次的結果立刻附加進 results.jsonl。回傳這次實際執行的次數。
    problems 是 {id: Problem}；client_factory(model) 回傳假的 client（只給測試）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    by_label = {model.label: model for model in models}
    todo = pending_runs(plan, results_path)
    for number, spec in enumerate(todo, start=1):
        model = by_label[spec.model]
        client = client_factory(model) if client_factory else None
        line = run_one(spec, problems[spec.problem], model, out_dir, client=client)
        with results_path.open("a", encoding="utf-8") as results:
            results.write(json.dumps(line, ensure_ascii=False) + "\n")
        progress(f"[{number}/{len(todo)}] {spec.problem} {spec.model} {spec.condition} #{spec.repeat}: "
                 f"{line['grade']['outcome']}" + (f" (error: {line['error']})" if line["error"] else ""))
    return len(todo)
