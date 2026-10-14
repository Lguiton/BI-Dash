"""Send a plain email through the SMTP settings in backend/.env. Mail only ever goes to the addresses in BI_REPORT_TO,
so nothing in the app can be used as an open mail relay."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


class MailError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message, self.status = message, status


def config() -> dict:
    to = [a.strip() for a in os.environ.get("BI_REPORT_TO", "").split(",") if a.strip()]
    user = os.environ.get("BI_SMTP_USER", "")
    return {"host": os.environ.get("BI_SMTP_HOST", ""), "port": int(os.environ.get("BI_SMTP_PORT", "587") or 587), "user": user,
            "password": os.environ.get("BI_SMTP_PASSWORD", ""), "from": os.environ.get("BI_SMTP_FROM", user),
            "security": os.environ.get("BI_SMTP_SECURITY", "starttls").lower(), "to": to}


def configured() -> bool:
    c = config()
    return bool(c["host"] and c["to"] and c["from"])


def send(subject: str, body: str, smtp_factory=None) -> list[str]:
    """Returns the recipients. `smtp_factory` lets tests replace the network."""
    c = config()
    if not (c["host"] and c["to"] and c["from"]):
        raise MailError("Email isn't configured. Set BI_SMTP_HOST, BI_SMTP_USER, BI_SMTP_PASSWORD and BI_REPORT_TO in backend/.env.", 503)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject[:200], c["from"], ", ".join(c["to"])
    msg.set_content(body)
    try:
        if smtp_factory:
            server = smtp_factory(c)
        elif c["security"] == "ssl":
            server = smtplib.SMTP_SSL(c["host"], c["port"], timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(c["host"], c["port"], timeout=20)
        with server:
            if c["security"] == "starttls" and not smtp_factory:
                server.starttls(context=ssl.create_default_context())
            if c["user"] and not smtp_factory:
                server.login(c["user"], c["password"])
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailError("The mail server rejected the username or password (Gmail needs an app password).") from None
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Couldn't send the email ({type(e).__name__}). Check BI_SMTP_HOST, port and security.") from None
    return c["to"]
