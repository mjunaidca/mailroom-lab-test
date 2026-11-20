import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import NoReturn

from mailroom.checks import check_issue
from mailroom.issue import Issue
from mailroom.signups import import_signups
from mailroom.subscribers import joined_since, next_send, read_subscribers


def subscribers(run_date: date, since_days: int | None = None) -> None:
    people = read_subscribers()
    if since_days is not None:
        print(f"Joined in last {since_days} days: {len(joined_since(people, run_date, since_days))}")
        return
    groups = Counter(s.group for s in people)
    print(f"Total: {len(people)}")
    for group, count in groups.items():
        print(f"{group}: {count}")


def import_file(path: Path, run_date: date) -> None:
    for result in import_signups(path, run_date):
        if result.reasons:
            print(f"rejected: {result.name} - {'; '.join(result.reasons)}")
        else:
            print(f"accepted: {result.name}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="mailroom.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p_sub = sub.add_parser("subscribers")
    p_sub.add_argument("--since-days", type=int)
    p_sub.add_argument("--run-date", type=date.fromisoformat)
    p_next = sub.add_parser("next-send")
    p_next.add_argument("--run-date", type=date.fromisoformat)
    p_check = sub.add_parser("check")
    p_check.add_argument("issue_file", type=Path)
    p_import = sub.add_parser("import")
    p_import.add_argument("file", type=Path)
    p_import.add_argument("--run-date", type=date.fromisoformat)
    args = parser.parse_args(argv[1:])

    if args.command == "check":
        print("\n".join(check_issue(Issue.from_text(args.issue_file.read_text())) or ["OK"]))
        return 0

    # The command line is the only place that reads today's date.
    run_date = args.run_date or date.today()
    if args.command == "import":
        import_file(args.file, run_date)
        return 0
    if args.command == "subscribers":
        subscribers(run_date, args.since_days)
    else:
        print(f"Next send: {next_send(run_date)}")
    return 0


def cli() -> NoReturn:
    sys.exit(main(sys.argv))
