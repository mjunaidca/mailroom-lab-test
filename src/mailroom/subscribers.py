import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError

from mailroom.problems import InputError, Problem

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


@dataclass(frozen=True)
class ReadResult:
    """Everything a read found: the good subscribers and every problem, in file order."""

    good: list[Subscriber]
    problems: list[Problem]


# (field, message) pairs; an extra rule for rows the model already accepted.
ExtraCheck = Callable[[Subscriber], list[tuple[str, str]]]


def read_subscribers(
    path: Path = SUBSCRIBERS_CSV, extra_check: ExtraCheck | None = None
) -> ReadResult:
    """Read a subscribers CSV. Bad rows become problems; only a bad file raises InputError."""
    if not path.is_file():
        raise InputError(f"I can't find the file {path}.")
    good: list[Subscriber] = []
    problems: list[Problem] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        expected = list(Subscriber.model_fields)
        found = reader.fieldnames or []
        if sorted(found) != sorted(expected):
            raise InputError(
                f"The columns in {path} are wrong: expected {', '.join(expected)} "
                f"but found {', '.join(found) or 'none'}."
            )
        for row in reader:
            name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            try:
                subscriber = Subscriber.model_validate(row)
            except ValidationError as error:
                problems += [
                    Problem(reader.line_num, name, str(e["loc"][0]), e["msg"])
                    for e in error.errors()
                ]
                continue
            found_here = extra_check(subscriber) if extra_check else []
            if found_here:
                problems += [Problem(reader.line_num, name, fld, msg) for fld, msg in found_here]
            else:
                good.append(subscriber)
    return ReadResult(good, problems)


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
