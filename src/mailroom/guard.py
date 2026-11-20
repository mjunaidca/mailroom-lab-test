"""The guard: reads a Claude Code hook's tool call and refuses mail to anyone who is not a practice address."""

import json

from pydantic import BaseModel, ConfigDict, ValidationError

from mailroom.problems import InputError
from mailroom.resend import check_recipient

GUARDED_TOOLS = ("send-email", "send-batch-emails")
ADDRESS_FIELDS = ("to", "cc", "bcc")


class Email(BaseModel):
    """The addresses of one email. Each field is one address or a list of them."""

    model_config = ConfigDict(extra="ignore")

    to: str | list[str] = []
    cc: str | list[str] = []
    bcc: str | list[str] = []

    def addresses(self) -> list[str]:
        found: list[str] = []
        for value in (self.to, self.cc, self.bcc):
            found += [value] if isinstance(value, str) else value
        return found


class ToolInput(BaseModel):
    """What a send tool is given: one email's fields, or a batch under `emails`."""

    model_config = ConfigDict(extra="ignore")

    to: str | list[str] = []
    cc: str | list[str] = []
    bcc: str | list[str] = []
    emails: list[Email] = []


class ToolCall(BaseModel):
    """A Claude Code hook's input, as far as the guard cares."""

    model_config = ConfigDict(extra="ignore")

    tool_name: str
    tool_input: ToolInput = ToolInput()


def read_call(text: str) -> ToolCall:
    try:
        return ToolCall.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError):
        raise InputError("I can't read that as a tool call: expected JSON with a tool_name.") from None


def is_guarded(tool_name: str) -> bool:
    """True for send-email and send-batch-emails, with or without an MCP prefix such as mcp__resend__."""
    return tool_name.rpartition("__")[2] in GUARDED_TOOLS


def reasons(call: ToolCall) -> list[str]:
    """Why the call must be refused: one reason per bad address, in order. Empty if fine."""
    if not is_guarded(call.tool_name):
        return []
    emails = [Email(to=call.tool_input.to, cc=call.tool_input.cc, bcc=call.tool_input.bcc), *call.tool_input.emails]
    found: list[str] = []
    for email in emails:
        for address in email.addresses():
            try:
                check_recipient(address)
            except InputError as error:
                found.append(str(error))
    return found
