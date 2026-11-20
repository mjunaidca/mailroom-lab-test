import hashlib
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from mailroom.issue import Issue
from mailroom.subscribers import Subscriber

PLAN_PATH = Path(__file__).parents[2] / "outbox" / "plan.json"


class Entry(BaseModel):
    """One planned email: who it goes to and exactly what it will say."""

    to: str
    subject: str
    text: str
    key: str  # the idempotency key: the same issue to the same address always has the same key


class Plan(BaseModel):
    """What a send would do on run_date. Nothing is sent from a plan."""

    run_date: date
    entries: list[Entry]


def idempotency_key(issue: Issue, to: str) -> str:
    """A key made from the issue (as written, before anyone's name is filled in) and the recipient. The server
    sends one email per key, so a repeated send of the same issue to the same address cannot arrive twice."""
    parts = [issue.subject or "", issue.preview or "", issue.body, to]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def build_plan(issue: Issue, subscribers: list[Subscriber], run_date: date) -> Plan:
    """One entry per subscriber, in order, with their first name filled in. Assumes the issue passed its check."""
    entries: list[Entry] = []
    for subscriber in subscribers:
        personal = issue.personalize(subscriber.first_name)
        entries.append(Entry(to=subscriber.email, subject=personal.subject or "", text=personal.body,
                          key=idempotency_key(issue, subscriber.email)))
    return Plan(run_date=run_date, entries=entries)


def write_plan(plan: Plan, path: Path = PLAN_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2) + "\n")
