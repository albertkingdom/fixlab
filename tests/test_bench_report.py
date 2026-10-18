# 彙整報告的測試：對應 experiment-report 規格。用手工做的結果行，不跑任何模型。
import json
from pathlib import Path

import pytest

from fixlab.bench.__main__ import main as bench_main
from fixlab.bench.problems import load_all, problem_digest
from fixlab.bench.report import paired_difference, render_report, tool_sequence
from fixlab.bench.runner import ModelConfig

TOY_ROOT = Path(__file__).resolve().parent / "fixtures" / "bench_toy"
PROBLEMS = {problem.id: problem for problem in load_all(TOY_ROOT)}
DIGEST = problem_digest(PROBLEMS["cart"])


def line(problem="cart", model="m", condition="with_tests", repeat=1, outcome="fixed", steps=4, prompt=1000, completion=200,
         error=None, claimed=False, hidden=0, log_path=None, digest=DIGEST):
    return {
        "problem": problem, "problem_digest": digest, "model": model, "condition": condition, "repeat": repeat,
        "grade": {"outcome": outcome, "fixed": outcome == "fixed"}, "stop_reason": "done" if error is None else "error",
        "steps": steps, "prompt_tokens": prompt, "completion_tokens": completion, "seconds": 3.0,
        "claimed_done_but_failed": claimed, "hidden_tool_calls": hidden, "log_path": log_path,
        "started_at": "2026-10-18T10:00:00+00:00", "error": error,
    }


def model(label="m", price=None):
    return ModelConfig(name=f"vendor/{label}", label=label, base_url=None, api_key_env="K", temperature=0.2,
                       extra_body={"seed": 1}, price=price, meta={"quantization": "Q4_K_M"})


def render(lines, models=None, **options):
    return render_report(lines, models if models is not None else [model()], PROBLEMS, **options)


def table_row(text, *start):
    """總表裡開頭是 start 的那一列，拆成欄位。"""
    for row in text.splitlines():
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if tuple(cells[:len(start)]) == start:
            return cells
    raise AssertionError(f"no row starting with {start}")


# Scenario: Counting outcomes
def test_the_summary_counts_outcomes_and_keeps_errors_apart():
    outcomes = ["fixed"] * 22 + ["broke_existing"] * 6 + ["overfit"] * 5 + ["unfixed"] * 5
    lines = [line(repeat=n, outcome=outcome) for n, outcome in enumerate(outcomes, start=1)]
    lines += [line(repeat=100 + n, error="boom") for n in range(2)]

    cells = table_row(render(lines), "m", "with_tests")

    assert cells[2] == "38"          # 算進結果的執行
    assert cells[3] == "22 (58%)"    # fixed
    assert cells[-1] == "2"          # 錯誤另外一欄


def test_the_summary_shows_claims_hidden_tool_calls_steps_and_tokens():
    lines = [line(repeat=1, outcome="unfixed", claimed=True, hidden=3, steps=5, prompt=1000, completion=100),
             line(repeat=2, outcome="fixed", steps=9, prompt=3000, completion=300)]

    cells = table_row(render(lines), "m", "with_tests")

    assert cells[8] == "1" and cells[9] == "0" and cells[10] == "3"  # 宣稱完成但沒修好、步數用完、叫了看不到的工具
    assert cells[11] == "7.0"                              # 步數中位數
    assert cells[12] == "2,000" and cells[13] == "200"    # token 平均


def test_only_the_latest_line_of_a_combination_is_used():
    lines = [line(repeat=1, outcome="unfixed", error="hiccup"), line(repeat=1, outcome="fixed")]

    cells = table_row(render(lines), "m", "with_tests")

    assert cells[2] == "1" and cells[3] == "1 (100%)" and cells[-1] == "0"


# ── paired comparison ─────────────────────────────────────────────────────

def paired_lines():
    """範例表：inventory 4/5 對 2/5，calendar 3/5 對 3/5。題目的名字用玩具題目的 id 以外的也可以，報告不要求題目存在。"""
    lines = []
    for problem, with_fixed, no_fixed in (("inventory", 4, 2), ("calendar", 3, 3)):
        for condition, fixed in (("with_tests", with_fixed), ("no_tests", no_fixed)):
            for n in range(5):
                lines.append(line(problem=problem, condition=condition, repeat=n + 1, outcome="fixed" if n < fixed else "unfixed"))
    return lines


# Scenario: Mean difference of two problems
def test_the_mean_difference_is_the_mean_of_the_per_problem_differences():
    result = paired_difference(paired_lines(), seed=0)

    assert result["problems"] == ["calendar", "inventory"]
    assert result["differences"] == pytest.approx([0.0, 0.4]) and result["mean"] == pytest.approx(0.2)
    assert "+0.20" in render(paired_lines())


# Scenario: Reproducible interval
def test_the_interval_is_the_same_every_time():
    first = render(paired_lines())
    second = render(paired_lines())

    assert first == second and "95% 區間" in first
    assert paired_difference(paired_lines(), 0)["low"] <= 0.2 <= paired_difference(paired_lines(), 0)["high"]


def test_a_model_with_only_one_condition_has_no_comparison():
    assert paired_difference([line(condition="with_tests")], seed=0) is None


# ── cost ──────────────────────────────────────────────────────────────────

# Scenario: Cost per fixed run
def test_cost_per_run_and_per_fixed_run():
    price = {"input_per_million": 0.10, "output_per_million": 0.40, "source": "OpenRouter page", "date": "2026-10-18"}
    lines = [line(repeat=n, outcome="fixed" if n <= 5 else "unfixed", prompt=100_000, completion=25_000) for n in range(1, 11)]

    text = render(lines, [model(price=price)])

    row = table_row(text, "m", "0.2000")
    assert row[2] == "0.0200" and row[3] == "0.0400"
    assert "OpenRouter page" in row[4] and "2026-10-18" in row[4]


# Scenario: No price
def test_without_a_price_only_tokens_are_shown():
    text = render([line()], [model(price=None)])

    cost_section = text.split("## 成本")[1].split("##")[0]
    assert "沒有單價" in cost_section and "$" not in cost_section
    assert "1,000" in table_row(text, "m", "with_tests")[12]


# ── examples, limits, warnings ────────────────────────────────────────────

# Scenario: Example of an overfit run
def test_a_failed_run_is_listed_with_its_tool_sequence_and_log(tmp_path):
    log = tmp_path / "events.jsonl"
    trace = lambda names: json.dumps({"event": "trace", "record": {"tool_calls": [{"name": name} for name in names]}})
    log.write_text("\n".join([json.dumps({"event": "run_start"}), trace(["run_tests"]), trace(["read_file"]), trace(["edit_file"]),
                              trace(["run_tests"]), json.dumps({"event": "task_end"})]))
    assert tool_sequence(log) == "run_tests, read_file, edit_file, run_tests"

    text = render([line(outcome="overfit", log_path=str(log))])

    example_section = text.split("### overfit")[1].split("##")[0]
    assert "run_tests, read_file, edit_file, run_tests" in example_section and str(log) in example_section


def test_at_most_the_requested_number_of_examples_per_outcome():
    lines = [line(repeat=n, outcome="unfixed") for n in range(1, 8)]

    text = render(lines, examples=2)

    assert text.split("### unfixed")[1].split("##")[0].count("- cart") == 2


# Scenario: Limits section
def test_the_last_section_states_the_limits():
    text = render([line()], examples=1)

    last = text.split("## ")[-1]
    assert last.startswith("限制")
    assert "只描述這一組題目" in last and "同一個行程" in last and "15 到 20 題降到 8 題" in last


# Scenario: A problem was edited after it was run
def test_a_digest_that_differs_from_the_current_problem_is_warned_about():
    text = render([line(digest="old-digest")])

    assert "## 警告" in text and "題目 cart 的摘要與目前的題目不同" in text and "## 結果總表" in text


def test_two_digests_for_one_problem_are_warned_about():
    text = render([line(repeat=1, digest="one"), line(repeat=2, digest="two")])

    assert "2 個不同的題目摘要" in text


def test_unequal_run_counts_are_warned_about():
    text = render([line(problem="cart", repeat=1), line(problem="cart", repeat=2), line(problem="other", repeat=1)])

    assert "各題的執行次數不一致" in text


def test_a_problem_that_does_not_exist_is_warned_about():
    assert "題目集沒有它" in render([line(problem="ghost")])


def test_the_report_command_prints_and_writes(tmp_path, capsys):
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps(line()) + "\n")

    assert bench_main(["report", str(results), "--problems-dir", str(TOY_ROOT)]) == 0
    printed = capsys.readouterr().out
    out = tmp_path / "report.md"
    assert bench_main(["report", str(results), "--problems-dir", str(TOY_ROOT), "--out", str(out)]) == 0

    assert "# 實驗報告" in printed and out.read_text().strip() == printed.strip()


def test_runs_that_used_up_their_steps_are_counted():
    lines = [line(repeat=1, outcome="fixed"), line(repeat=2, outcome="fixed"), line(repeat=3, outcome="unfixed")]
    lines[0]["stop_reason"] = "max_steps"
    lines[2]["stop_reason"] = "max_steps"

    assert table_row(render(lines), "m", "with_tests")[9] == "2"


def test_the_examples_section_says_so_when_every_run_was_fixed():
    text = render([line(outcome="fixed")])

    assert "沒有：所有算進結果的執行都是 fixed" in text.split("## 失敗實例")[1].split("##")[0]


# ── code review：沒有任何算進結果的執行時，報告不能崩潰 ──────────────────────

PRICE = {"input_per_million": 0.10, "output_per_million": 0.40, "source": "page", "date": "2026-10-18"}


def test_a_priced_model_whose_every_run_failed_does_not_crash_the_report():
    lines = [line(repeat=1, error="404"), line(repeat=2, error="404")]

    text = render(lines, [model(price=PRICE)])

    cost_row = table_row(text, "m", "-")
    assert "沒有算進結果的執行" in cost_row[4]
    assert table_row(text, "m", "with_tests")[2] == "0" and table_row(text, "m", "with_tests")[-1] == "2"


def test_runs_without_a_step_count_do_not_crash_the_median():
    text = render([line(steps=None)])

    assert table_row(text, "m", "with_tests")[11] == "-"
