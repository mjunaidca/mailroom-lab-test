"""Sending a whole plan to the practice server."""

import asyncio
import time

import httpx

from mailroom.plan import Entry, Plan
from mailroom.resend import Sent, Settings, check_recipient, check_server, send_entry, send_entry_async


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


async def send_all_at_once(
    plan: Plan, settings: Settings, client: httpx.AsyncClient, latency: float, limit: int
) -> list[Sent]:
    """Send the plan with at most `limit` requests in flight at once. Each one waits `latency` seconds before its
    request, so the waits overlap. The results come back in the plan's order, however the requests finish.
    If some fail, all are allowed to finish and the first failure in the plan's order is raised."""
    check_plan(plan, settings)
    room = asyncio.Semaphore(limit)

    async def one(entry: Entry) -> Sent:
        async with room:
            await asyncio.sleep(latency)
            return await send_entry_async(client, settings, entry)

    outcomes = await asyncio.gather(*(one(entry) for entry in plan.entries), return_exceptions=True)
    sent: list[Sent] = []
    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            raise outcome
        sent.append(outcome)
    return sent
