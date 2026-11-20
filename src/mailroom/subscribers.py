import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

SUBSCRIBERS_CSV = Path(__file__).parents[2] / "data" / "subscribers.csv"


@dataclass(frozen=True)
class Subscriber:
    first_name: str
    last_name: str
    email: str
    group: str
    joined_on: date
    consent: str


def read_subscribers() -> list[Subscriber]:
    with SUBSCRIBERS_CSV.open(newline="") as f:
        return [
            Subscriber(
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                group=row["group"],
                joined_on=date.fromisoformat(row["joined_on"]),
                consent=row["consent"],
            )
            for row in csv.DictReader(f)
        ]


def joined_since(
    subscribers: list[Subscriber], run_date: date, days: int
) -> list[Subscriber]:
    """Subscribers who joined within the last `days` days, counting the boundary day."""
    cutoff = run_date - timedelta(days=days)
    return [s for s in subscribers if cutoff <= s.joined_on <= run_date]


def next_send(run_date: date) -> date:
    """First Monday of the month after run_date's month."""
    if run_date.month == 12:
        first = date(run_date.year + 1, 1, 1)
    else:
        first = date(run_date.year, run_date.month + 1, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7)
