"""python -m fixlab.bench 的入口：grade（對一個工作目錄評分）、check（題目自我檢查）、run（實驗）、report（報告）。"""

import argparse
import json
import sys
from pathlib import Path

from fixlab.bench.grader import grade
from fixlab.bench.problems import PROBLEMS_DIR, load_all, load_problem
from fixlab.bench.selfcheck import DEFAULT_REPEAT, check_problem, check_problem_set


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
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
