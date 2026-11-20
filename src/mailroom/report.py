"""What a send left behind (outbox/sent.json) and what it adds up to."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from mailroom.plan import Plan
from mailroom.problems import InputError
from mailroom.resend import Sent
from mailroom.subscribers import GROUPS, Subscriber

SENT_PATH = Path(__file__).parents[2] / "outbox" / "sent.json"
SENT = "sent"


class Record(BaseModel):
    """One email the server was given: its id, who it went to, and what became of it."""

    id: str
    to: str
    status: str


_RECORDS = TypeAdapter(list[Record])


@dataclass(frozen=True)
class Report:
    per_group: dict[str, int]  # every group, in order, with how many of its members got an email
    failures: list[Record]


def records_of(plan: Plan, sent: list[Sent]) -> list[Record]:
    """Match each result to its entry. Results come back in the plan's order."""
    return [Record(id=s.id, to=e.to, status=SENT) for e, s in zip(plan.entries, sent, strict=True)]


def write_sent(records: list[Record], path: Path = SENT_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(_RECORDS.dump_json(records, indent=2).decode() + "\n")


def read_sent(path: Path = SENT_PATH) -> list[Record]:
    if not path.is_file():
        raise InputError(f"I can't find {path}: send an issue first.")
    try:
        return _RECORDS.validate_json(path.read_text())
    except ValidationError:
        raise InputError(f"{path} is not a list of sent emails.") from None


def build_report(records: list[Record], subscribers: list[Subscriber]) -> Report:
    group_of = {s.email: s.group for s in subscribers}
    got = Counter(group_of.get(r.to, "unknown") for r in records if r.status == SENT)
    per_group = {group: got[group] for group in GROUPS}
    return Report(per_group, [r for r in records if r.status != SENT])
