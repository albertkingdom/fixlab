"""彙整報告：把 results.jsonl 變成回答專案問題的數字與實例，輸出 markdown。

回答的問題：有沒有 run_tests 差多少？沒有 run_tests 時 agent 會不會宣稱完成卻沒修好？花多少錢？
報告裡的每個數字都能從原始檔重現（信賴區間用固定的亂數種子）。結論只寫「在這組題目上觀察到」。
"""

import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from fixlab.bench.problems import problem_digest
from fixlab.bench.runner import CONDITIONS, latest_by_key

OUTCOMES = ("fixed", "broke_existing", "overfit", "invalid", "unfixed")
BOOTSTRAP_ROUNDS = 2000
LIMITS = (
    "- 題數與次數：這份報告只用了上面列的題目與次數，結果只描述這一組題目，不能推到別的題目或別的模型。",
    "- 被測的程式與 pytest 在同一個行程，可以偽造測試結果（例如印假的摘要再結束）。評分器用固定參數、乾淨環境重跑、"
    "只讀最後一行摘要、比對通過數與不自動載入外掛來降低風險，不能根治，所以數字只是降低了這個風險。",
    "- 題數由原本計畫的 15 到 20 題降到 8 題，這項調整是在寫任何一題之前決定的，不是看了結果才改。",
)


def percent(count: int, total: int) -> str:
    return f"{count} ({round(100 * count / total)}%)" if total else f"{count} (-)"


def counted(lines: list) -> list:
    """算進結果的執行：沒有錯誤的。有錯誤的另外算。"""
    return [line for line in lines if line["error"] is None]


def mean(values: list):
    return sum(values) / len(values) if values else None


def median_of(values: list):
    return statistics.median(values) if values else None


def number(value, digits=0) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def group_by(lines: list, key) -> dict:
    groups = defaultdict(list)
    for line in lines:
        groups[key(line)].append(line)
    return groups


def cost_of(lines: list, price: dict | None):
    """這些執行的總成本；沒有單價（或沒有 token 數）就是 None。"""
    if not price:
        return None
    total = 0.0
    for line in lines:
        total += (line["prompt_tokens"] or 0) / 1_000_000 * price["input_per_million"]
        total += (line["completion_tokens"] or 0) / 1_000_000 * price["output_per_million"]
    return total


def paired_difference(lines: list, seed: int) -> dict | None:
    """同一個模型：每題的（有 run_tests 修好比例）減（沒有的修好比例），平均，以及對題目重抽樣的 95% 區間。"""
    rates = {"with_tests": {}, "no_tests": {}}
    for condition in rates:
        for problem, group in group_by([l for l in counted(lines) if l["condition"] == condition], lambda l: l["problem"]).items():
            rates[condition][problem] = sum(l["grade"]["fixed"] for l in group) / len(group)
    problems = sorted(set(rates["with_tests"]) & set(rates["no_tests"]))
    if not problems:
        return None
    differences = [rates["with_tests"][p] - rates["no_tests"][p] for p in problems]
    generator = random.Random(seed)
    means = sorted(mean([generator.choice(differences) for _ in differences]) for _ in range(BOOTSTRAP_ROUNDS))
    return {"problems": problems, "rates": rates, "differences": differences, "mean": mean(differences),
            "low": means[int(0.025 * BOOTSTRAP_ROUNDS)], "high": means[int(0.975 * BOOTSTRAP_ROUNDS) - 1]}


def tool_sequence(log_path) -> str:
    """事件檔裡 agent 依序呼叫的工具名稱；讀不到就是空字串。"""
    if not log_path or not Path(log_path).exists():
        return ""
    names = []
    for text in Path(log_path).read_text(encoding="utf-8").splitlines():
        event = json.loads(text)
        if event.get("event") == "trace":
            names += [call["name"] for call in event["record"].get("tool_calls", [])]
    return ", ".join(names)


def find_warnings(lines: list, all_lines: list, problems: dict) -> list:
    warnings = []
    digests = group_by(all_lines, lambda l: l["problem"])
    for problem_id, group in sorted(digests.items()):
        if problem_id not in problems:
            warnings.append(f"結果裡有題目 {problem_id}，但目前的題目集沒有它")
            continue
        seen = {line["problem_digest"] for line in group}
        if len(seen) > 1:
            warnings.append(f"題目 {problem_id} 的結果有 {len(seen)} 個不同的題目摘要：題目在實驗中途被改過")
        elif seen != {problem_digest(problems[problem_id])}:
            warnings.append(f"題目 {problem_id} 的摘要與目前的題目不同：結果是用另一個版本的題目跑的")
    per_cell = group_by(lines, lambda l: (l["model"], l["condition"]))
    for (model, condition), group in sorted(per_cell.items()):
        sizes = {problem: len(runs) for problem, runs in group_by(group, lambda l: l["problem"]).items()}
        if len(set(sizes.values())) > 1:
            warnings.append(f"{model} / {condition}：各題的執行次數不一致（{sizes}）")
    return warnings


def render_report(all_lines: list, models: list, problems: dict, examples: int = 3, seed: int = 0) -> str:
    lines = list(latest_by_key(all_lines).values())  # 同一組合有多行時只用最後一行
    by_label = {model.label: model for model in models}
    out = ["# 實驗報告", ""]

    # ── 實驗設定 ──
    labels = sorted({line["model"] for line in lines})
    problem_ids = sorted({line["problem"] for line in lines})
    repeats = sorted({line["repeat"] for line in lines})
    starts = sorted(line["started_at"] for line in lines) if lines else []
    out += ["## 實驗設定", "",
            f"- 題目：{len(problem_ids)} 題（{', '.join(problem_ids)}）",
            f"- 條件：{', '.join(c for c in CONDITIONS if any(l['condition'] == c for l in lines))}",
            f"- 每個（題目、模型、條件）的次數：{repeats[0] if repeats else 0} 到 {repeats[-1] if repeats else 0}；共 {len(lines)} 次執行",
            f"- 時間：{starts[0] if starts else '-'} 到 {starts[-1] if starts else '-'}"]
    for label in labels:
        model = by_label.get(label)
        if model is None:
            out.append(f"- 模型 {label}：設定檔裡沒有這個模型")
            continue
        out.append(f"- 模型 {label}：{model.name}，temperature {model.temperature}，extra_body {json.dumps(model.extra_body)}，"
                   f"紀錄的條件 {json.dumps(model.meta, ensure_ascii=False)}")
    out.append("")

    # ── 總表 ──
    out += ["## 結果總表", "",
            "| 模型 | 條件 | 執行數 | " + " | ".join(OUTCOMES) + " | 宣稱完成但沒修好 | 步數用完 | 叫了看不到的工具 | 步數中位數 | prompt token 平均 | completion token 平均 | 錯誤 |",
            "|" + "---|" * (len(OUTCOMES) + 10)]
    cells = group_by(lines, lambda l: (l["model"], l["condition"]))
    for (label, condition), group in sorted(cells.items()):
        ok = counted(group)
        by_outcome = {name: sum(1 for l in ok if l["grade"]["outcome"] == name) for name in OUTCOMES}
        out.append("| " + " | ".join([
            label, condition, str(len(ok)), *[percent(by_outcome[name], len(ok)) for name in OUTCOMES],
            str(sum(1 for l in ok if l["claimed_done_but_failed"])), str(sum(1 for l in ok if l["stop_reason"] == "max_steps")),
            str(sum(l["hidden_tool_calls"] for l in ok)),
            number(median_of([l["steps"] for l in ok if l["steps"] is not None]), 1),
            number(mean([l["prompt_tokens"] for l in ok if l["prompt_tokens"] is not None])),
            number(mean([l["completion_tokens"] for l in ok if l["completion_tokens"] is not None])),
            str(len(group) - len(ok))]) + " |")
    out.append("")

    # ── 成本 ──
    out += ["## 成本", "", "| 模型 | 總成本 | 每次 | 每修好一題 | 單價（每百萬 token 的輸入／輸出，來源，日期） |", "|---|---|---|---|---|"]
    for label in labels:
        ok = counted([l for l in lines if l["model"] == label])
        price = (by_label.get(label).price if label in by_label else None)
        total = cost_of(ok, price)
        if not ok:
            out.append(f"| {label} | - | - | - | 沒有算進結果的執行（全部是錯誤），算不出成本 |")
            continue
        if total is None:
            out.append(f"| {label} | - | - | - | 沒有單價，只列 token（見上表） |")
            continue
        fixed = sum(1 for l in ok if l["grade"]["fixed"])
        out.append(f"| {label} | {total:.4f} | {total / len(ok):.4f} | {number(total / fixed if fixed else None, 4)} | "
                   f"{price['input_per_million']} / {price['output_per_million']}，{price['source']}，{price['date']} |")
    out.append("")

    # ── 成對比較 ──
    out += ["## 有無 run_tests 的比較（同一題成對）", ""]
    any_pair = False
    for label in labels:
        result = paired_difference([l for l in lines if l["model"] == label], seed)
        if result is None:
            continue
        any_pair = True
        out += [f"### {label}", "", "| 題目 | 有 run_tests 修好比例 | 沒有 run_tests 修好比例 | 差 |", "|---|---|---|---|"]
        for problem, difference in zip(result["problems"], result["differences"]):
            out.append(f"| {problem} | {result['rates']['with_tests'][problem]:.2f} | {result['rates']['no_tests'][problem]:.2f} | {difference:+.2f} |")
        out += ["", f"平均差 {result['mean']:+.2f}，95% 區間 [{result['low']:+.2f}, {result['high']:+.2f}]"
                    f"（對 {len(result['problems'])} 題重抽樣 {BOOTSTRAP_ROUNDS} 次，亂數種子 {seed}）", ""]
    if not any_pair:
        out += ["沒有任何模型同時有兩個條件的結果。", ""]

    # ── 每題 ──
    out += ["## 每題修好的比例", "", "| 題目 | " + " | ".join(f"{label} {c}" for label in labels for c in CONDITIONS) + " |",
            "|" + "---|" * (1 + len(labels) * len(CONDITIONS))]
    for problem in problem_ids:
        row = [problem]
        for label in labels:
            for condition in CONDITIONS:
                ok = counted([l for l in lines if (l["problem"], l["model"], l["condition"]) == (problem, label, condition)])
                row.append(f"{sum(1 for l in ok if l['grade']['fixed'])}/{len(ok)}" if ok else "-")
        out.append("| " + " | ".join(row) + " |")
    out.append("")

    # ── 失敗實例 ──
    out += ["## 失敗實例", ""]
    if all(line["grade"]["outcome"] == "fixed" for line in counted(lines)):
        out += ["沒有：所有算進結果的執行都是 fixed。", ""]
    for outcome in OUTCOMES[1:]:
        picked = [l for l in counted(lines) if l["grade"]["outcome"] == outcome][:examples]
        if not picked:
            continue
        out += [f"### {outcome}", ""]
        for line in picked:
            out.append(f"- {line['problem']} / {line['model']} / {line['condition']} / 第 {line['repeat']} 次：{line['stop_reason']}，"
                       f"{line['steps']} 步；工具呼叫：{tool_sequence(line['log_path']) or '-'}；事件檔：{line['log_path']}")
        out.append("")

    # ── 警告 ──
    warnings = find_warnings(lines, all_lines, problems)
    if warnings:
        out += ["## 警告", ""] + [f"- {text}" for text in warnings] + [""]

    # ── 限制（一定放在最後） ──
    out += ["## 限制", ""] + list(LIMITS) + [""]
    return "\n".join(out)
