import argparse
import csv
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

SUBSCRIBERS_CSV = Path(__file__).parent / "data" / "subscribers.csv"


def read_subscribers():
    with SUBSCRIBERS_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def joined_since(rows, run_date, days):
    """Rows that joined within the last `days` days, counting the boundary day."""
    cutoff = run_date - timedelta(days=days)
    return [r for r in rows if cutoff <= date.fromisoformat(r["joined_on"]) <= run_date]


def next_send(run_date):
    """First Monday of the month after run_date's month."""
    if run_date.month == 12:
        first = date(run_date.year + 1, 1, 1)
    else:
        first = date(run_date.year, run_date.month + 1, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7)


MAX_SUBJECT_LENGTH = 50
MAX_PREVIEW_LENGTH = 90
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(https?://[^)\s]+\)")


def check_subject(issue_text):
    """Return a list of problems with the issue's Subject line; empty if fine."""
    for line in issue_text.splitlines():
        if line.startswith("Subject:"):
            subject = line[len("Subject:"):].strip()
            if not subject:
                return ["empty"]
            if len(subject) > MAX_SUBJECT_LENGTH:
                return ["too long"]
            return []
    return ["missing"]


def check_issue(issue_text):
    """Return a list of every problem in the issue; empty if fine."""
    problems = [f"subject: {p}" for p in check_subject(issue_text)]
    lines = issue_text.splitlines()

    for line in lines:
        if line.startswith("Preview:"):
            if len(line[len("Preview:"):].strip()) > MAX_PREVIEW_LENGTH:
                problems.append("preview: too long")
            break

    if "{{first_name}}" not in issue_text:
        problems.append("greeting: missing {{first_name}}")

    links = LINK_PATTERN.findall(issue_text)
    if len(links) != 1:
        problems.append(f"link: expected exactly 1, found {len(links)}")

    has_reason = any(line.startswith("You're getting this because") for line in lines)
    has_unsubscribe = any("Unsubscribe: {{unsubscribe_url}}" in line for line in lines)
    if not (has_reason and has_unsubscribe):
        problems.append("footer: missing or incomplete")

    return problems


def subscribers(run_date, since_days=None):
    rows = read_subscribers()
    if since_days is not None:
        print(f"Joined in last {since_days} days: {len(joined_since(rows, run_date, since_days))}")
        return
    groups = Counter(row["group"] for row in rows)
    print(f"Total: {len(rows)}")
    for group, count in groups.items():
        print(f"{group}: {count}")


def main(argv):
    parser = argparse.ArgumentParser(prog="mailroom.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p_sub = sub.add_parser("subscribers")
    p_sub.add_argument("--since-days", type=int)
    p_sub.add_argument("--run-date", type=date.fromisoformat)
    p_next = sub.add_parser("next-send")
    p_next.add_argument("--run-date", type=date.fromisoformat)
    p_check = sub.add_parser("check")
    p_check.add_argument("issue_file", type=Path)
    args = parser.parse_args(argv[1:])

    if args.command == "check":
        print("\n".join(check_issue(args.issue_file.read_text()) or ["OK"]))
        return 0

    # The command line is the only place that reads today's date.
    run_date = args.run_date or date.today()
    if args.command == "subscribers":
        subscribers(run_date, args.since_days)
    else:
        print(f"Next send: {next_send(run_date)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
