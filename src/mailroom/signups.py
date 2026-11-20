from datetime import date
from pathlib import Path

from mailroom.rules import check_signup
from mailroom.subscribers import ReadResult, read_subscribers


def read_signups(path: Path, run_date: date) -> ReadResult:
    """Read a sign-up file: the model first, then our rules. Bad rows become problems."""
    return read_subscribers(path, lambda subscriber: check_signup(subscriber, run_date))
