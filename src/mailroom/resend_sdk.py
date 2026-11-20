"""The same one-email send as resend.send_entry, written with the official `resend` package."""

import resend as resend_sdk

from mailroom.plan import Entry
from mailroom.resend import SENDER, Sent, Settings, check_recipient, check_server


def send_entry_sdk(settings: Settings, entry: Entry) -> Sent:
    """Send one planned email through the package. Both guards run before anything goes out."""
    check_server(settings)
    check_recipient(entry.to)
    resend_sdk.api_url = settings.url.rstrip("/")  # the package reads RESEND_API_URL once, at import
    resend_sdk.api_key = settings.key
    params: resend_sdk.Emails.SendParams = {
        "from": SENDER,
        "to": [entry.to],
        "subject": entry.subject,
        "text": entry.text,
    }
    created = resend_sdk.Emails.send(params)
    return Sent(status_code=200, id=created["id"])  # the package does not hand back the status code
