"""Talking to the practice mail server. Skeleton only: the checks come first."""

from collections.abc import Mapping

import httpx
from pydantic import BaseModel

from mailroom.issue import Issue


class Settings(BaseModel):
    url: str
    key: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        raise NotImplementedError


class Sent(BaseModel):
    status_code: int
    id: str


def send_email(client: httpx.Client, settings: Settings, to: str, issue: Issue) -> Sent:
    raise NotImplementedError


def get_status(client: httpx.Client, settings: Settings, email_id: str) -> str:
    raise NotImplementedError
