# 實驗執行器的測試：對應 experiment-runner 規格。用玩具題目與假的模型 client，不呼叫任何真的 LLM。
import json
import os
import shutil
from pathlib import Path

import pytest

from fixlab.bench import runner
from fixlab.bench.__main__ import main as bench_main
from fixlab.bench.problems import load_all, load_problem, problem_digest
from fixlab.bench.runner import (ModelConfig, RunSpec, fixlab_arguments, latest_by_key, pending_runs, plan_runs,
                                 read_results, run_experiment, run_one)
from test_loop import FakeClient, native

TOY_ROOT = Path(__file__).resolve().parent / "fixtures" / "bench_toy"
FIX = native("edit_file", path="shop/cart.py", old_string="quantity > DISCOUNT_FROM", new_string="quantity >= DISCOUNT_FROM")


def model(label="fake", **changes):
    settings = dict(name=f"vendor/{label}", label=label, base_url="http://fake.example/v1", api_key_env="FAKE_KEY",
                    meta={"quantization": "Q4_K_M"})
    settings.update(changes)
    return ModelConfig(**settings)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("FAKE_KEY", "secret-for-tests")


@pytest.fixture
def problem():
    return load_problem(TOY_ROOT / "cart")


@pytest.fixture
def many_problems(tmp_path):
    """玩具題目的八份副本（p1 到 p8），用來測 8 題的計畫。"""
    root = tmp_path / "many"
    for number in range(1, 9):
        copy = root / f"p{number}"
        shutil.copytree(TOY_ROOT / "cart", copy, ignore=shutil.ignore_patterns("__pycache__"))
        data = json.loads((copy / "problem.json").read_text())
        data["id"] = f"p{number}"
        (copy / "problem.json").write_text(json.dumps(data))
    return root


def models_file(folder, labels=("a", "b"), **changes):
    entries = [{"name": f"vendor/{label}", "label": label, "base_url": "http://fake.example/v1",
                "api_key_env": "FAKE_KEY", **changes} for label in labels]
    path = folder / "models.json"
    path.write_text(json.dumps({"models": entries}))
    return path


def factory(*replies_per_run):
    """每次執行拿到一個新的假 client；劇本一份一份用完，最後一份重複使用。"""
    scripts = list(replies_per_run)

    def make(model):
        return FakeClient(list(scripts.pop(0) if len(scripts) > 1 else scripts[0]))
    return make


SOLVE = [(None, [FIX]), ("Done.", None)]
DO_NOTHING = [("Done.", None)]


# ── The plan is shown and nothing runs without confirmation ───────────────

# Scenario: Plan only
def test_without_confirmation_only_the_plan_is_printed(many_problems, tmp_path, capsys):
    out = tmp_path / "out"

    code = bench_main(["run", "--models", str(models_file(tmp_path)), "--out", str(out), "--problems-dir", str(many_problems)])

    printed = capsys.readouterr().out
    assert code == 0 and "160 runs" in printed and "--confirm" in printed
    assert not (out / "results.jsonl").exists()


def test_the_plan_puts_the_repeat_outermost():
    plan = plan_runs(["p1", "p2"], [model("a")], ["with_tests", "no_tests"], 2)

    assert [spec.repeat for spec in plan] == [1, 1, 1, 1, 2, 2, 2, 2]
    assert len(plan) == 8


def test_an_unknown_condition_is_rejected(tmp_path, capsys):
    code = bench_main(["run", "--models", str(models_file(tmp_path)), "--out", str(tmp_path / "o"),
                       "--problems-dir", str(TOY_ROOT), "--conditions", "with_tests,sometimes"])

    assert code == 2 and "sometimes" in capsys.readouterr().err


# ── Model settings come from a file and secrets from the environment ──────

# Scenario: Missing key
def test_a_missing_api_key_stops_everything_with_exit_code_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FAKE_KEY")
    out = tmp_path / "out"

    code = bench_main(["run", "--models", str(models_file(tmp_path)), "--out", str(out),
                       "--problems-dir", str(TOY_ROOT), "--confirm"])

    assert code == 2 and "FAKE_KEY" in capsys.readouterr().err
    assert not (out / "results.jsonl").exists()


# Scenario: No sandbox
def test_formal_runs_are_refused_without_the_sandbox(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("fixlab.bench.__main__.sandbox_available", lambda: False)
    out = tmp_path / "out"

    code = bench_main(["run", "--models", str(models_file(tmp_path)), "--out", str(out),
                       "--problems-dir", str(TOY_ROOT), "--confirm"])

    assert code == 2 and "sandbox" in capsys.readouterr().err
    assert not (out / "results.jsonl").exists()


def test_the_model_file_has_no_key_and_the_environment_is_restored(problem, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://original/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    run_one(RunSpec("cart", "fake", "with_tests", 1), problem, model(), tmp_path, client=FakeClient(list(DO_NOTHING)))

    assert os.environ["OPENAI_BASE_URL"] == "http://original/v1" and "OPENAI_API_KEY" not in os.environ


# ── The two conditions differ only in the visible tools ───────────────────

# Scenario: Arguments of the two conditions
def test_the_two_conditions_differ_only_in_the_condition_meta_and_the_hidden_tool(tmp_path):
    with_tests = fixlab_arguments(tmp_path, model(temperature=0.2, extra_body={"seed": 1}), RunSpec("cart", "fake", "with_tests", 3), "abc", tmp_path / "log")
    no_tests = fixlab_arguments(tmp_path, model(temperature=0.2, extra_body={"seed": 1}), RunSpec("cart", "fake", "no_tests", 3), "abc", tmp_path / "log")

    assert "--hide-tool" not in with_tests
    assert no_tests[-2:] == ["--hide-tool", "run_tests"]
    assert [a.replace("no_tests", "with_tests") for a in no_tests[:-2]] == with_tests
    assert "--temperature" in with_tests and "0.2" in with_tests and '{"seed": 1}' in with_tests


# ── Each run uses a fresh copy of the problem ─────────────────────────────

# Scenario: Runs do not affect each other
def test_a_second_run_starts_from_the_original_project(problem, tmp_path):
    results = run_experiment({"cart": problem}, [model()], plan_runs(["cart"], [model()], ["with_tests"], 2), tmp_path,
                             client_factory=factory(SOLVE, DO_NOTHING), progress=lambda text: None)

    lines = read_results(tmp_path / "results.jsonl")
    assert results == 2 and [line["grade"]["outcome"] for line in lines] == ["fixed", "unfixed"]


# ── The conditions of each run are recorded / results are one line per run ──

# Scenario: Meta of a run
def test_a_run_records_its_conditions_in_run_start(problem, tmp_path):
    line = run_one(RunSpec("cart", "fake", "no_tests", 3), problem, model(), tmp_path, client=FakeClient(list(DO_NOTHING)))

    events = [json.loads(text) for text in Path(line["log_path"]).read_text().splitlines()]
    run_start = events[0]
    assert run_start["meta"] == {"problem": "cart", "condition": "no_tests", "repeat": "3",
                                 "problem_digest": problem_digest(problem), "quantization": "Q4_K_M"}
    assert run_start["base_url"] == "http://fake.example/v1" and run_start["hidden_tools"] == ["run_tests"]


def test_a_solved_run_produces_a_complete_result_line(problem, tmp_path):
    line = run_one(RunSpec("cart", "fake", "with_tests", 1), problem, model(), tmp_path, client=FakeClient(list(SOLVE)))

    assert line["grade"]["outcome"] == "fixed" and line["stop_reason"] == "done" and line["steps"] == 2
    assert (line["prompt_tokens"], line["completion_tokens"]) == (20, 10)  # 假 client 每次回覆 10 + 5
    assert line["claimed_done_but_failed"] is False and line["hidden_tool_calls"] == 0 and line["error"] is None
    assert line["problem_digest"] == problem_digest(problem) and Path(line["log_path"]).exists()
    assert set(line) == {"problem", "problem_digest", "model", "condition", "repeat", "grade", "stop_reason", "steps",
                         "prompt_tokens", "completion_tokens", "seconds", "claimed_done_but_failed",
                         "hidden_tool_calls", "log_path", "started_at", "error"}


# Scenario: Claiming done without fixing
def test_claiming_done_without_fixing_is_marked(problem, tmp_path):
    line = run_one(RunSpec("cart", "fake", "with_tests", 1), problem, model(), tmp_path, client=FakeClient(list(DO_NOTHING)))

    assert line["stop_reason"] == "done" and line["grade"]["fixed"] is False
    assert line["claimed_done_but_failed"] is True


# Scenario: Counting calls to a hidden tool
def test_calls_to_a_hidden_tool_are_counted(problem, tmp_path):
    replies = [(None, [native("run_tests")])] * 3 + [("Done.", None)]

    line = run_one(RunSpec("cart", "fake", "no_tests", 1), problem, model(), tmp_path, client=FakeClient(replies))

    assert line["hidden_tool_calls"] == 3 and line["stop_reason"] == "done"


# ── Resume and errors ─────────────────────────────────────────────────────

# Scenario: Resuming an interrupted experiment
def test_only_the_missing_combinations_are_pending(tmp_path):
    plan = plan_runs([f"p{n}" for n in range(1, 9)], [model("a"), model("b")], ["with_tests", "no_tests"], 5)
    assert len(plan) == 160
    results = tmp_path / "results.jsonl"
    results.write_text("".join(
        json.dumps({"problem": s.problem, "model": s.model, "condition": s.condition, "repeat": s.repeat, "error": None}) + "\n"
        for s in plan[:37]))

    assert len(pending_runs(plan, results)) == 123


def test_the_experiment_runs_only_what_is_pending(problem, tmp_path):
    plan = plan_runs(["cart"], [model()], ["with_tests", "no_tests"], 2)  # 4 次
    run_experiment({"cart": problem}, [model()], plan[:1], tmp_path, client_factory=factory(DO_NOTHING), progress=lambda text: None)

    executed = run_experiment({"cart": problem}, [model()], plan, tmp_path, client_factory=factory(DO_NOTHING), progress=lambda text: None)

    assert executed == 3 and len(read_results(tmp_path / "results.jsonl")) == 4


# Scenario: Retrying errors on resume
def test_a_combination_with_an_error_is_run_again_and_the_latest_line_counts(problem, tmp_path):
    spec = RunSpec("cart", "fake", "with_tests", 1)
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"problem": "cart", "model": "fake", "condition": "with_tests", "repeat": 1,
                                   "error": "provider hiccup", "marker": "old"}) + "\n")

    executed = run_experiment({"cart": problem}, [model()], [spec], tmp_path, client_factory=factory(SOLVE), progress=lambda text: None)

    lines = read_results(results)
    assert executed == 1 and len(lines) == 2
    assert latest_by_key(lines)[spec.key]["grade"]["outcome"] == "fixed"


# Scenario: The provider rejects the request
def test_a_failed_request_is_recorded_as_an_error_and_the_next_run_still_happens(problem, tmp_path):
    plan = plan_runs(["cart"], [model()], ["with_tests"], 2)
    failing_then_fine = [[RuntimeError("provider rejected temperature")], SOLVE]

    run_experiment({"cart": problem}, [model()], plan, tmp_path, client_factory=factory(*failing_then_fine), progress=lambda text: None)

    first, second = read_results(tmp_path / "results.jsonl")
    assert first["stop_reason"] == "error" and "provider rejected temperature" in first["error"]
    assert first["grade"]["outcome"] == "unfixed"  # 錯誤的執行仍然評分
    assert second["error"] is None and second["grade"]["outcome"] == "fixed"


def test_load_models_reads_the_file(tmp_path):
    path = models_file(tmp_path, labels=("x",), temperature=0.1, meta={"runtime": "OpenRouter"},
                       price={"input_per_million": 0.1, "output_per_million": 0.4, "source": "page", "date": "2026-10-18"})

    (loaded,) = runner.load_models(path)

    assert loaded.label == "x" and loaded.temperature == 0.1 and loaded.meta == {"runtime": "OpenRouter"}
    assert loaded.price["source"] == "page"


# ── code review：設定與參數的防呆 ──────────────────────────────────────────

# Scenario: A repeat count below 1
@pytest.mark.parametrize("command", [["run", "--repeats", "0"], ["run", "--repeats", "-2"], ["check", "--repeat", "0"]])
def test_a_repeat_count_below_one_is_rejected(tmp_path, command):
    arguments = [*command, "--problems-dir", str(TOY_ROOT)]
    if command[0] == "run":
        arguments += ["--models", str(models_file(tmp_path)), "--out", str(tmp_path / "out")]

    with pytest.raises(SystemExit) as stopped:
        bench_main(arguments)

    assert stopped.value.code == 2


# Scenario: A model entry uses a reserved meta key
@pytest.mark.parametrize("key", ["problem", "condition", "repeat", "problem_digest"])
def test_a_model_meta_that_uses_a_reserved_key_is_rejected(tmp_path, key):
    path = models_file(tmp_path, labels=("x",), meta={key: "x"})

    with pytest.raises(runner.ConfigError, match=key):
        runner.load_models(path)


# Scenario: A model without a base URL
def test_a_model_without_a_base_url_does_not_inherit_the_callers_endpoint(problem, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://callers-endpoint/v1")

    line = run_one(RunSpec("cart", "fake", "with_tests", 1), problem, model(base_url=None), tmp_path, client=FakeClient(list(DO_NOTHING)))

    run_start = json.loads(Path(line["log_path"]).read_text().splitlines()[0])
    assert run_start["base_url"] is None  # 沒寫 base_url 的模型不能走呼叫者環境裡的端點
    assert os.environ["OPENAI_BASE_URL"] == "http://callers-endpoint/v1"  # 執行完還原


# ── code review 第二輪：更多防呆 ───────────────────────────────────────────

@pytest.mark.parametrize("command", [["run", "--repeats", "abc"], ["run", "--repeats", "1.5"], ["check", "--repeat", "abc"]])
def test_a_repeat_count_that_is_not_an_integer_is_rejected(tmp_path, command):
    arguments = [*command, "--problems-dir", str(TOY_ROOT)]
    if command[0] == "run":
        arguments += ["--models", str(models_file(tmp_path)), "--out", str(tmp_path / "out")]

    with pytest.raises(SystemExit) as stopped:
        bench_main(arguments)

    assert stopped.value.code == 2


def test_the_plan_itself_refuses_a_repeat_count_below_one():
    with pytest.raises(runner.ConfigError, match="repeats"):
        plan_runs(["p1"], [model()], ["with_tests"], 0)


@pytest.mark.parametrize("meta", [None, ["quantization"], "Q4_K_M"])
def test_a_model_meta_that_is_not_an_object_is_a_configuration_error(tmp_path, meta):
    path = models_file(tmp_path, labels=("x",), meta=meta)

    with pytest.raises(runner.ConfigError, match="meta"):
        runner.load_models(path)
