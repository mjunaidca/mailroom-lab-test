import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import NoReturn

import httpx

from mailroom.checks import check_issue
from mailroom.issue import Issue, read_issue
from mailroom.plan import Plan, build_plan, write_plan
from mailroom.problems import InputError, Problem
from mailroom.report import SENT_PATH, build_report, read_sent, records_of, write_sent
from mailroom.resend import Sent, Settings, get_status, send_email
from mailroom.sending import send_all, send_all_at_once
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


async def send_plan_at_once(
    plan: Plan, settings: Settings, latency: float, limit: int, transport: httpx.AsyncBaseTransport | None
) -> list[Sent]:
    async with httpx.AsyncClient(timeout=10, transport=transport) as client:
        return await send_all_at_once(plan, settings, client, latency, limit)


def send_now(
    issue_file: Path,
    run_date: date,
    settings: Settings,
    latency: float,
    transport: httpx.BaseTransport | None = None,
    at_once: int | None = None,
    async_transport: httpx.AsyncBaseTransport | None = None,
    sent_path: Path = SENT_PATH,
) -> int:
    """Check the issue, plan it, send the whole plan one by one, and say how long it took."""
    issue = read_issue(issue_file)
    issue_problems = check_issue(issue)
    if issue_problems:
        print("\n".join(issue_problems))
        return 1
    result = read_subscribers()
    if result.problems:
        print_problems(result.problems)
        return 1
    plan = build_plan(issue, result.good, run_date)
    started = time.perf_counter()
    if at_once is None:
        with httpx.Client(timeout=10, transport=transport) as client:
            sent = send_all(plan, settings, client, latency)
    else:
        sent = asyncio.run(send_plan_at_once(plan, settings, latency, at_once, async_transport))
    write_sent(records_of(plan, sent), sent_path)
    print(f"Sent {len(sent)} emails in {time.perf_counter() - started:.2f} seconds")
    return 0


def report(sent_path: Path = SENT_PATH) -> int:
    """Say how many emails each group got, and list every email that did not go out."""
    built = build_report(read_sent(sent_path), read_subscribers().good)
    for group, count in built.per_group.items():
        print(f"{group}: {count}")
    if not built.failures:
        print("Failures: none")
    else:
        print(f"Failures: {len(built.failures)}")
        for r in built.failures:
            print(f"failed: {r.to} - {r.id}: {r.status}")
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


def non_negative_seconds(text: str) -> float:
    try:
        seconds = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"latency must be a number of seconds, not {text!r}") from None
    if not seconds >= 0:
        raise argparse.ArgumentTypeError(f"latency cannot be negative, not {text!r}")
    return seconds


def at_least_one(text: str) -> int:
    try:
        count = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"at-once must be a whole number, not {text!r}") from None
    if count < 1:
        raise argparse.ArgumentTypeError(f"at-once must be at least 1, not {text!r}")
    return count


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
    p_send.add_argument("--dry-run", action="store_true")
    p_send.add_argument("--run-date", type=date.fromisoformat)
    p_send.add_argument("--latency", type=non_negative_seconds, default=0.0)
    p_send.add_argument("--at-once", type=at_least_one)
    sub.add_parser("report")
    p_one = sub.add_parser("send-one")
    p_one.add_argument("issue_file", type=Path)
    p_one.add_argument("--to", required=True)
    args = parser.parse_args(argv[1:])
    if args.command == "send" and args.dry_run and args.latency:
        parser.error("--latency has no meaning with --dry-run, which sends nothing")
    if args.command == "send" and args.dry_run and args.at_once:
        parser.error("--at-once has no meaning with --dry-run, which sends nothing")

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
        if args.command == "send" and args.dry_run:
            return send(args.issue_file, run_date)
        if args.command == "send":
            return send_now(args.issue_file, run_date, Settings.from_env(os.environ), args.latency, at_once=args.at_once)
        if args.command == "report":
            return report()
        if args.command == "subscribers":
            return subscribers(run_date, args.since_days)
    except InputError as error:
        print(error, file=sys.stderr)
        return 2
    print(f"Next send: {next_send(run_date)}")
    return 0


def cli() -> NoReturn:
    sys.exit(main(sys.argv))
