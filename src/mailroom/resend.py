"""Talking to the practice mail server. Sending works only against localhost, and only to practice addresses."""

from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from mailroom.issue import Issue
from mailroom.problems import InputError

DEFAULT_URL = "http://localhost:4000"
DEFAULT_KEY = "re_practice"
SENDER = "onboarding@resend.dev"
ALLOWED_RECIPIENT_DOMAINS = ("example.com", "resend.dev")
# The test address has no first name, so the greeting reads "Hi there,".
STAND_IN_NAME = "there"


class Settings(BaseModel):
    url: str
    key: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        return cls(url=env.get("RESEND_API_URL", DEFAULT_URL), key=env.get("RESEND_API_KEY", DEFAULT_KEY))


class Sent(BaseModel):
    status_code: int
    id: str


class _Created(BaseModel):
    id: str


class _Fetched(BaseModel):
    last_event: str


def check_server(settings: Settings) -> None:
    """Refuse unless the server's host is exactly localhost."""
    try:
        host = urlsplit(settings.url).hostname
    except ValueError:
        host = None
    if host != "localhost":
        raise InputError(f"I will only send to a server on localhost, not {settings.url}.")


def check_recipient(to: str) -> None:
    """Refuse any recipient not at @example.com or @resend.dev."""
    name, at, domain = to.partition("@")
    if not name or not at or "@" in domain or domain.lower() not in ALLOWED_RECIPIENT_DOMAINS:
        raise InputError(f"I will only send to @example.com or @resend.dev addresses, not {to}.")


def _call(client: httpx.Client, settings: Settings, method: str, path: str, json: dict[str, object] | None = None) -> httpx.Response:
    """One request to the server. Any failure becomes one plain sentence."""
    try:
        response = client.request(
            method, settings.url.rstrip("/") + path, json=json, headers={"Authorization": f"Bearer {settings.key}"}
        )
    except httpx.TransportError:
        raise InputError(f"I can't reach the practice server at {settings.url}. Is it running?") from None
    if response.status_code >= 400:
        raise InputError(f"The practice server answered {response.status_code} to {method} {path}.")
    return response


def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
    try:
        return model.model_validate_json(response.content)
    except ValidationError:
        raise InputError("The practice server's answer was not what I expected.") from None


def send_email(client: httpx.Client, settings: Settings, to: str, issue: Issue) -> Sent:
    """Send one issue to one address. Assumes the issue passed its check. Both guards run before anything goes out."""
    check_server(settings)
    check_recipient(to)
    personal = issue.personalize(STAND_IN_NAME)
    payload: dict[str, object] = {"from": SENDER, "to": [to], "subject": personal.subject, "text": personal.body}
    response = _call(client, settings, "POST", "/emails", payload)
    return Sent(status_code=response.status_code, id=_parse(_Created, response).id)


def get_status(client: httpx.Client, settings: Settings, email_id: str) -> str:
    """Ask the server what happened to an email."""
    check_server(settings)
    return _parse(_Fetched, _call(client, settings, "GET", f"/emails/{email_id}")).last_event
