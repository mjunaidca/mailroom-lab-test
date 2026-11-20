import argparse
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import NoReturn

import httpx

from mailroom.checks import check_issue
from mailroom.issue import Issue, read_issue
from mailroom.plan import build_plan, write_plan
from mailroom.problems import InputError, Problem
from mailroom.resend import Settings, get_status, send_email
from mailroom.signups import read_signups
from mailroom.subscribers import joined_since, next_send, read_subscribers


def print_problems(problems: list[Problem]) -> None:
    for p in problems:
        print(f"rejected: {p.name} - row {p.row}, {p.field}: {p.message}")


def subscribers(run_date: date, since_days: int | None = None) -> int:
    result = read_subscribers()
    if result.problems:
        print_problems(result.problems)
        return 1
    people = result.good
    if since_days is not None:
        print(f"Joined in last {since_days} days: {len(joined_since(people, run_date, since_days))}")
        return 0
    groups = Counter(s.group for s in people)
    print(f"Total: {len(people)}")
    for group, count in groups.items():
        print(f"{group}: {count}")
    return 0


def import_file(path: Path, run_date: date) -> int:
    result = read_signups(path, run_date)
    for subscriber in result.good:
        print(f"accepted: {subscriber.first_name} {subscriber.last_name}")
    print_problems(result.problems)
    return 1 if result.problems else 0


def send(issue_file: Path, run_date: date) -> int:
    """Dry run: check the issue, then write the plan. Nothing is written if anything is wrong."""
    issue = read_issue(issue_file)
    issue_problems = check_issue(issue)
    if issue_problems:
        print("\n".join(issue_problems))
        return 1
    result = read_subscribers()
    if result.problems:
        print_problems(result.problems)
        return 1
    write_plan(build_plan(issue, result.good, run_date))
    print(f"Planned {len(result.good)} emails for {run_date}")
    return 0


def send_one(issue_file: Path, to: str, settings: Settings, client: httpx.Client) -> int:
    """Send the issue to one practice address, then ask the server what became of it."""
    issue = read_issue(issue_file)
    issue_problems = check_issue(issue)
    if issue_problems:
        print("\n".join(issue_problems))
        return 1
    sent = send_email(client, settings, to, issue)
    print(f"Sent: {sent.status_code} {sent.id}")
    print(f"Status: {get_status(client, settings, sent.id)}")
    return 0


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
    p_send = sub.add_parser("send")
    p_send.add_argument("issue_file", type=Path)
    p_send.add_argument("--dry-run", action="store_true", required=True)
    p_send.add_argument("--run-date", type=date.fromisoformat)
    p_one = sub.add_parser("send-one")
    p_one.add_argument("issue_file", type=Path)
    p_one.add_argument("--to", required=True)
    args = parser.parse_args(argv[1:])

    if args.command == "check":
        print("\n".join(check_issue(Issue.from_text(args.issue_file.read_text())) or ["OK"]))
        return 0

    if args.command == "send-one":
        try:
            with httpx.Client(timeout=10) as client:
                return send_one(args.issue_file, args.to, Settings.from_env(os.environ), client)
        except InputError as error:
            print(error, file=sys.stderr)
            return 2

    # The command line is the only place that reads today's date.
    run_date = args.run_date or date.today()
    try:
        if args.command == "import":
            return import_file(args.file, run_date)
        if args.command == "send":
            return send(args.issue_file, run_date)
        if args.command == "subscribers":
            return subscribers(run_date, args.since_days)
    except InputError as error:
        print(error, file=sys.stderr)
        return 2
    print(f"Next send: {next_send(run_date)}")
    return 0


def cli() -> NoReturn:
    sys.exit(main(sys.argv))
