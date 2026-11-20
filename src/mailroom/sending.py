"""Sending a whole plan to the practice server."""

import httpx

from mailroom.plan import Plan
from mailroom.resend import Sent, Settings


def send_all(plan: Plan, settings: Settings, client: httpx.Client, latency: float) -> list[Sent]:
    raise NotImplementedError
