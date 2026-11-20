from dataclasses import dataclass


class InputError(Exception):
    """The user's input can't be read at all (no file, wrong columns). Message is one plain sentence."""


@dataclass(frozen=True)
class Problem:
    """One thing wrong with one field of one row. Row 1 is the header line."""

    row: int
    name: str
    field: str
    message: str
