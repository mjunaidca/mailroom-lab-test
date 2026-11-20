import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

SUBSCRIBERS_CSV = Path(__file__).parents[2] / "data" / "subscribers.csv"


class Subscriber(BaseModel):
    """One subscriber. Anything from outside must be validated through this."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    first_name: str
    last_name: str
    email: EmailStr
    group: Literal["tea-curious", "gift-buyers", "daily-drinkers"]
    joined_on: date
    consent: str = Field(min_length=1)


def read_subscribers() -> list[Subscriber]:
    with SUBSCRIBERS_CSV.open(newline="") as f:
        return [Subscriber.model_validate(row) for row in csv.DictReader(f)]


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
