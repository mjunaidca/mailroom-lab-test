import csv
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from mailroom.subscribers import Subscriber


@dataclass(frozen=True)
class ImportResult:
    name: str
    subscriber: Subscriber | None
    reasons: list[str]


def import_signups(path: Path) -> list[ImportResult]:
    """Validate every row of a sign-ups CSV through Subscriber; never raises on bad rows."""
    results: list[ImportResult] = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
            try:
                results.append(ImportResult(name, Subscriber.model_validate(row), []))
            except ValidationError as error:
                reasons = [
                    f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}"
                    for e in error.errors()
                ]
                results.append(ImportResult(name, None, reasons))
    return results
