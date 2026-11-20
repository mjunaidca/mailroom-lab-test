import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from mailroom.rules import check_signup
from mailroom.subscribers import Subscriber


@dataclass(frozen=True)
class ImportResult:
    name: str
    subscriber: Subscriber | None
    reasons: list[str]


def import_signups(path: Path, run_date: date) -> list[ImportResult]:
    """Validate every row through Subscriber, then apply our rules; never raises on bad rows."""
    results: list[ImportResult] = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
            try:
                subscriber = Subscriber.model_validate(row)
                problems = check_signup(subscriber, run_date)
                results.append(ImportResult(name, None if problems else subscriber, problems))
            except ValidationError as error:
                reasons = [
                    f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}"
                    for e in error.errors()
                ]
                results.append(ImportResult(name, None, reasons))
    return results
