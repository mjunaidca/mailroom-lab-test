"""Talking to the practice mail server. Sending works only against localhost, and only to practice addresses."""

from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from mailroom.issue import Issue
from mailroom.plan import Entry
from mailroom.problems import InputError

DEFAULT_URL = "http://localhost:4000"
DEFAULT_KEY = "re_practice"
START_COMMAND = "npx emulate@0.12.3 start --service resend"
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


class _Refusal(BaseModel):
    message: str


def _unreachable(settings: Settings) -> InputError:
    return InputError(f"The practice server is not running at {settings.url}. Start it with: {START_COMMAND}")


def _answer(response: httpx.Response, method: str, path: str, unknown_id: str | None) -> httpx.Response:
    """Handle each status on purpose. A 4xx is the server's final answer, so nothing here ever retries."""
    status = response.status_code
    if status == 422:
        try:
            reason = _Refusal.model_validate_json(response.content).message
        except ValidationError:
            reason = "it did not say why"
        raise InputError(f"The practice server refused it: {reason}")
    if status == 404 and unknown_id is not None:
        raise InputError(f"The practice server has no email with the id {unknown_id}: the id is unknown.")
    if status >= 400:
        raise InputError(f"The practice server answered {status} to {method} {path}.")
    return response


def _call(
    client: httpx.Client,
    settings: Settings,
    method: str,
    path: str,
    json: dict[str, object] | None = None,
    unknown_id: str | None = None,
) -> httpx.Response:
    """One request to the server, made exactly once. Each failure becomes one plain sentence."""
    try:
        response = client.request(
            method, settings.url.rstrip("/") + path, json=json, headers={"Authorization": f"Bearer {settings.key}"}
        )
    except httpx.TransportError:
        raise _unreachable(settings) from None
    return _answer(response, method, path, unknown_id)


async def _call_async(
    client: httpx.AsyncClient, settings: Settings, method: str, path: str, json: dict[str, object]
) -> httpx.Response:
    """The same one request as _call, for the async client."""
    try:
        response = await client.request(
            method, settings.url.rstrip("/") + path, json=json, headers={"Authorization": f"Bearer {settings.key}"}
        )
    except httpx.TransportError:
        raise _unreachable(settings) from None
    return _answer(response, method, path, None)


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
    return _parse(_Fetched, _call(client, settings, "GET", f"/emails/{email_id}", unknown_id=email_id)).last_event


def send_entry(client: httpx.Client, settings: Settings, entry: Entry) -> Sent:
    """Send one planned email. Both guards run before anything goes out."""
    check_server(settings)
    check_recipient(entry.to)
    payload: dict[str, object] = {"from": SENDER, "to": [entry.to], "subject": entry.subject, "text": entry.text}
    response = _call(client, settings, "POST", "/emails", payload)
    return Sent(status_code=response.status_code, id=_parse(_Created, response).id)


async def send_entry_async(client: httpx.AsyncClient, settings: Settings, entry: Entry) -> Sent:
    """send_entry for the async client. Both guards run before anything goes out."""
    check_server(settings)
    check_recipient(entry.to)
    payload: dict[str, object] = {"from": SENDER, "to": [entry.to], "subject": entry.subject, "text": entry.text}
    response = await _call_async(client, settings, "POST", "/emails", payload)
    return Sent(status_code=response.status_code, id=_parse(_Created, response).id)
