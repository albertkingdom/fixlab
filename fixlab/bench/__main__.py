"""python -m fixlab.bench 的入口：grade（對一個工作目錄評分）、check（題目自我檢查）、run（實驗）、report（報告）。"""

import argparse
import json
import sys
from pathlib import Path

from fixlab.bench.grader import grade
from fixlab.bench.problems import PROBLEMS_DIR, load_problem


def add_problems_dir(parser) -> None:
    parser.add_argument("--problems-dir", default=str(PROBLEMS_DIR), help="where the problem folders are (default: bench/problems)")


def command_grade(args) -> int:
    problem = load_problem(Path(args.problems_dir) / args.problem)
    print(json.dumps(grade(problem, args.workdir), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m fixlab.bench", description="fixlab benchmark")
    commands = parser.add_subparsers(dest="command", required=True)

    grade_parser = commands.add_parser("grade", help="grade an agent's working directory against the hidden tests")
    grade_parser.add_argument("problem", help="problem id, e.g. inventory")
    grade_parser.add_argument("workdir", help="the working directory the agent left behind")
    add_problems_dir(grade_parser)
    grade_parser.set_defaults(func=command_grade)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
