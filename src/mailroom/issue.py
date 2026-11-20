import re
from dataclasses import dataclass, replace
from pathlib import Path

from mailroom.problems import InputError

MAX_SUBJECT_LENGTH = 50
MAX_PREVIEW_LENGTH = 90
LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")


@dataclass(frozen=True)
class Issue:
    """One newsletter issue. subject/preview are None when the line is absent."""

    subject: str | None
    preview: str | None
    body: str

    @classmethod
    def from_text(cls, text: str) -> "Issue":
        subject: str | None = None
        preview: str | None = None
        lines = text.splitlines()
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("Subject:") and subject is None:
                subject = line[len("Subject:"):].strip()
            elif line.startswith("Preview:") and preview is None:
                preview = line[len("Preview:"):].strip()
            else:
                break
            start = i + 1
        body = "\n".join(lines[start:]).strip("\n")
        return cls(subject, preview, body)

    @property
    def links(self) -> list[str]:
        """The URLs of every [text](url) link in the body, in order."""
        return LINK_PATTERN.findall(self.body)

    def personalize(self, first_name: str) -> "Issue":
        """A copy with {{first_name}} filled in; {{unsubscribe_url}} is left alone."""

        def fill(text: str | None) -> str | None:
            return None if text is None else text.replace("{{first_name}}", first_name)

        return replace(
            self,
            subject=fill(self.subject),
            preview=fill(self.preview),
            body=self.body.replace("{{first_name}}", first_name),
        )


def read_issue(path: Path) -> Issue:
    """Read an issue file. A missing file raises InputError."""
    if not path.is_file():
        raise InputError(f"I can't find the file {path}.")
    return Issue.from_text(path.read_text())
