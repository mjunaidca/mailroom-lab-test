import csv
import sys
from collections import Counter
from pathlib import Path

SUBSCRIBERS_CSV = Path(__file__).parent / "data" / "subscribers.csv"


def subscribers():
    with SUBSCRIBERS_CSV.open(newline="") as f:
        rows = list(csv.DictReader(f))
    groups = Counter(row["group"] for row in rows)
    print(f"Total: {len(rows)}")
    for group, count in groups.items():
        print(f"{group}: {count}")


def main(argv):
    if argv[1:] == ["subscribers"]:
        subscribers()
        return 0
    print("usage: mailroom.py subscribers", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
