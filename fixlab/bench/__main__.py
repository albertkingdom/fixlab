"""python -m fixlab.bench 的入口：grade（對一個工作目錄評分）、check（題目自我檢查）、run（實驗）、report（報告）。"""

import argparse
import json
import os
import sys
from pathlib import Path

from fixlab.bench.grader import grade
from fixlab.bench.problems import PROBLEMS_DIR, load_all, load_problem
from fixlab.bench import report, runner
from fixlab.bench.selfcheck import DEFAULT_REPEAT, check_problem, check_problem_set
from fixlab.sandbox import sandbox_available


def add_problems_dir(parser) -> None:
    parser.add_argument("--problems-dir", default=str(PROBLEMS_DIR), help="where the problem folders are (default: bench/problems)")


def command_grade(args) -> int:
    problem = load_problem(Path(args.problems_dir) / args.problem)
    print(json.dumps(grade(problem, args.workdir), ensure_ascii=False, indent=2))
    return 0


def command_check(args) -> int:
    problems_dir = Path(args.problems_dir)
    if args.problem:
        problems = [load_problem(problems_dir / name) for name in args.problem]
    else:
        problems = load_all(problems_dir)

    failed = False
    if not args.problem and problems_dir == PROBLEMS_DIR:  # 預設的題目集要剛好是固定的八題
        for reason in check_problem_set(problems):
            print(f"benchmark: FAILED - {reason}")
            failed = True
    for problem in problems:
        result = check_problem(problem, repeat=args.repeat)
        if result.ok:
            print(f"{problem.id}: passed")
        else:
            failed = True
            print(f"{problem.id}: FAILED")
            for reason in result.reasons:
                print(f"  - {reason}")
    return 1 if failed else 0


def command_run(args) -> int:
    problems_dir = Path(args.problems_dir)
    try:
        models = runner.load_models(args.models)
        conditions = [name.strip() for name in args.conditions.split(",")]
        for name in conditions:
            if name not in runner.CONDITIONS:
                raise runner.ConfigError(f"unknown condition {name!r} (conditions: {', '.join(runner.CONDITIONS)})")
        names = args.problem or [problem.id for problem in load_all(problems_dir)]
        problems = {name: load_problem(problems_dir / name) for name in names}
    except (runner.ConfigError, ValueError, OSError) as error:
        print(f"fixlab.bench: error: {error}", file=sys.stderr)
        return 2

    plan = runner.plan_runs(names, models, conditions, args.repeats)
    out_dir = Path(args.out)
    results_path = out_dir / "results.jsonl"
    todo = runner.pending_runs(plan, results_path)
    print(f"{len(plan)} runs: {len(names)} problems x {len(models)} models x {len(conditions)} conditions x {args.repeats} repeats")
    print(f"models: {', '.join(model.label for model in models)}")
    print(f"conditions: {', '.join(conditions)}")
    print(f"results file: {results_path} ({len(plan) - len(todo)} done, {len(todo)} to run)")
    if not args.confirm:
        print("this is only the plan: every run calls a model and costs money; add --confirm to run it")
        return 0

    missing = [model.api_key_env for model in models if not os.environ.get(model.api_key_env)]
    if missing:
        print(f"fixlab.bench: error: environment variable not set: {', '.join(missing)}", file=sys.stderr)
        return 2
    if not sandbox_available():
        print("fixlab.bench: error: the sandbox is not available, so the agent's test runs could read the hidden tests; "
              "formal runs need the sandbox", file=sys.stderr)
        return 2
    runner.run_experiment(problems, models, plan, out_dir)
    return 0


def command_report(args) -> int:
    try:
        lines = runner.read_results(args.results)
        models = runner.load_models(args.models) if args.models else []
        problems = {problem.id: problem for problem in load_all(Path(args.problems_dir))}
    except (runner.ConfigError, ValueError, OSError) as error:
        print(f"fixlab.bench: error: {error}", file=sys.stderr)
        return 2
    text = report.render_report(lines, models, problems, examples=args.examples)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m fixlab.bench", description="fixlab benchmark")
    commands = parser.add_subparsers(dest="command", required=True)

    grade_parser = commands.add_parser("grade", help="grade an agent's working directory against the hidden tests")
    grade_parser.add_argument("problem", help="problem id, e.g. inventory")
    grade_parser.add_argument("workdir", help="the working directory the agent left behind")
    add_problems_dir(grade_parser)
    grade_parser.set_defaults(func=command_grade)

    check_parser = commands.add_parser("check", help="verify the problems without calling any model")
    check_parser.add_argument("problem", nargs="*", help="problem ids to check (default: all)")
    check_parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                              help=f"how many times to repeat every run to catch flaky tests (default: {DEFAULT_REPEAT})")
    add_problems_dir(check_parser)
    check_parser.set_defaults(func=command_check)

    run_parser = commands.add_parser("run", help="run the experiment (prints the plan; add --confirm to really run)")
    run_parser.add_argument("--models", required=True, help="JSON file describing the models")
    run_parser.add_argument("--out", required=True, help="folder for results.jsonl and the event logs")
    run_parser.add_argument("--problem", action="append", help="only this problem id (repeatable; default: all)")
    run_parser.add_argument("--conditions", default=",".join(runner.CONDITIONS), help="comma separated (default: both)")
    run_parser.add_argument("--repeats", type=int, default=5, help="runs per problem, model and condition (default: 5)")
    run_parser.add_argument("--confirm", action="store_true", help="really call the models; every run costs money")
    add_problems_dir(run_parser)
    run_parser.set_defaults(func=command_run)

    report_parser = commands.add_parser("report", help="turn results.jsonl into a markdown report")
    report_parser.add_argument("results", help="the results.jsonl written by the run command")
    report_parser.add_argument("--models", help="the models JSON file (for settings and prices)")
    report_parser.add_argument("--examples", type=int, default=3, help="failed runs to list per outcome (default: 3)")
    report_parser.add_argument("--out", help="write the report to this file instead of printing it")
    add_problems_dir(report_parser)
    report_parser.set_defaults(func=command_report)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
