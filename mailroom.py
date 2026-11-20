import argparse
import csv
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
    args = parser.parse_args(argv[1:])

    # The command line is the only place that reads today's date.
    run_date = args.run_date or date.today()
    if args.command == "subscribers":
        subscribers(run_date, args.since_days)
    else:
        print(f"Next send: {next_send(run_date)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
