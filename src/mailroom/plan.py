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


class Plan(BaseModel):
    """What a send would do on run_date. Nothing is sent from a plan."""

    run_date: date
    entries: list[Entry]


def build_plan(issue: Issue, subscribers: list[Subscriber], run_date: date) -> Plan:
    """One entry per subscriber, in order, with their first name filled in. Assumes the issue passed its check."""
    entries: list[Entry] = []
    for subscriber in subscribers:
        personal = issue.personalize(subscriber.first_name)
        entries.append(Entry(to=subscriber.email, subject=personal.subject or "", text=personal.body))
    return Plan(run_date=run_date, entries=entries)


def write_plan(plan: Plan, path: Path = PLAN_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2) + "\n")
