import csv
from datetime import date, timedelta
from pathlib import Path

SUBSCRIBERS_CSV = Path(__file__).parents[2] / "data" / "subscribers.csv"


def read_subscribers() -> list[dict[str, str]]:
    with SUBSCRIBERS_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def joined_since(
    rows: list[dict[str, str]], run_date: date, days: int
) -> list[dict[str, str]]:
    """Rows that joined within the last `days` days, counting the boundary day."""
    cutoff = run_date - timedelta(days=days)
    return [r for r in rows if cutoff <= date.fromisoformat(r["joined_on"]) <= run_date]


def next_send(run_date: date) -> date:
    """First Monday of the month after run_date's month."""
    if run_date.month == 12:
        first = date(run_date.year + 1, 1, 1)
    else:
        first = date(run_date.year, run_date.month + 1, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7)
