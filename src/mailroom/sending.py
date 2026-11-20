"""Sending a whole plan to the practice server."""

import time

import httpx

from mailroom.plan import Plan
from mailroom.resend import Sent, Settings, check_recipient, check_server, send_entry


def check_plan(plan: Plan, settings: Settings) -> None:
    """Refuse the whole plan, before the first request, if the server or any recipient is not a practice one."""
    check_server(settings)
    for entry in plan.entries:
        check_recipient(entry.to)


def send_all(plan: Plan, settings: Settings, client: httpx.Client, latency: float) -> list[Sent]:
    """Send the plan one by one, in its order, waiting `latency` seconds before each request."""
    check_plan(plan, settings)
    sent: list[Sent] = []
    for entry in plan.entries:
        time.sleep(latency)
        sent.append(send_entry(client, settings, entry))
    return sent
