from datetime import date

from mailroom.subscribers import Subscriber

ALLOWED_DOMAIN = "example.com"


def check_signup(subscriber: Subscriber, run_date: date) -> list[tuple[str, str]]:
    """Kettlebird's own rules for a sign-up the model already accepted, as (field, message); empty if fine."""
    problems: list[tuple[str, str]] = []
    if subscriber.email.rpartition("@")[2].lower() != ALLOWED_DOMAIN:
        problems.append(("email", f"must be at @{ALLOWED_DOMAIN}"))
    if subscriber.joined_on > run_date:
        problems.append(("joined_on", f"{subscriber.joined_on} is after run date {run_date}"))
    return problems
