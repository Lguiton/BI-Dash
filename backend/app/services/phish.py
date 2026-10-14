"""Phishing practice: safe, made-up emails to judge (phish or real?), with the tells explained afterwards.

Every address and link uses the reserved .example and example.com names, which cannot reach a real site. Nothing here sends or opens anything. Real phishing can look much
better than these, so the lesson is the habit (check the sender, the link target, the urgency, the request) and not memorising examples."""
from __future__ import annotations

import random

MAILS = [
    {"id": "p1", "phish": True, "from_name": "PayPal Support", "from_addr": "service@paypa1-secure.example", "subject": "Your account is limited: act within 24 hours", "body": "We noticed unusual activity. To avoid permanent suspension, confirm your details now.", "links": [{"text": "Confirm my account", "href": "https://paypa1-login.example/verify"}], "attachment": "",
     "tells": ["The sender domain is 'paypa1' with the number 1, not the real name.", "Threat of suspension and a 24-hour deadline create panic.", "The button goes to a different site than the sender claims to be."]},
    {"id": "p2", "phish": True, "from_name": "Your Boss", "from_addr": "owner.gmail-mail@example.example", "subject": "Quick favour, are you at your desk?", "body": "I'm in a meeting and can't talk. Need you to buy 4 gift cards for a client today and send me the codes. I'll reimburse you.", "links": [], "attachment": "",
     "tells": ["Gift cards are almost never a real business request.", "A personal address is used for a supposed work request.", "It asks you not to phone: 'can't talk'.", "Urgency and secrecy together. Check by phoning a number you already have."]},
    {"id": "p3", "phish": True, "from_name": "Invoice Dept", "from_addr": "billing@supplier-docs.example", "subject": "Invoice 88213 overdue", "body": "Please see the attached invoice. Enable editing and enable content to view it.", "links": [], "attachment": "Invoice_88213.xlsm",
     "tells": ["A macro-enabled file (.xlsm) sent as an invoice.", "It tells you to 'enable content', which is how macros run.", "You were not expecting this supplier or invoice number."]},
    {"id": "p4", "phish": True, "from_name": "IT Helpdesk", "from_addr": "it-helpdesk@company-support.example", "subject": "Password expires today", "body": "Your password expires today. Click below to keep your current password.", "links": [{"text": "https://company.example/password", "href": "https://company-password-reset.example/login"}], "attachment": "",
     "tells": ["The visible link text and the real destination are different.", "Real IT rarely asks you to click a link to keep a password.", "Generic greeting and a same-day deadline."]},
    {"id": "p5", "phish": True, "from_name": "Delivery Notice", "from_addr": "tracking@parcel-update.example", "subject": "Your parcel is waiting: pay $1.99 redelivery fee", "body": "We tried to deliver your parcel. Pay the small fee to rebook delivery.", "links": [{"text": "Rebook delivery", "href": "https://parcel-fee.example/pay"}], "attachment": "",
     "tells": ["You may not be expecting any parcel.", "A tiny fee is a way to capture card details.", "Sender and link are not the carrier's real domain."]},
    {"id": "p6", "phish": True, "from_name": "Microsoft 365", "from_addr": "no-reply@m1crosoft-365.example", "subject": "Shared document: Payroll 2026", "body": "Dana shared a file with you. Sign in to view.", "links": [{"text": "Open document", "href": "https://m1crosoft-365-docs.example/signin"}], "attachment": "",
     "tells": ["'m1crosoft' uses the number 1.", "A sign-in page reached from an email link is a classic credential grab.", "Curiosity bait: payroll."]},
    {"id": "p7", "phish": True, "from_name": "Bank Security", "from_addr": "alerts@bank-secure-alert.example", "subject": "Unrecognised sign-in. Call us now", "body": "We blocked a sign-in from another country. Call the number below immediately to cancel the transfer: +1 555 0100.", "links": [], "attachment": "",
     "tells": ["It pushes you to phone a number in the email, not the one on your card.", "Urgency and a scary event.", "The sender domain is not your bank's."]},
    {"id": "l1", "phish": False, "from_name": "Your Accountant", "from_addr": "sam@yourfirm.example", "subject": "Notes from Tuesday's call", "body": "Thanks for the call. As discussed, send me the October statements when you can. No rush this week.", "links": [], "attachment": "",
     "legit_why": "Known sender, matches a conversation you had, no urgency, no link, nothing to click."},
    {"id": "l2", "phish": False, "from_name": "Calendar", "from_addr": "calendar@yourcompany.example", "subject": "Reminder: staff meeting Thursday 10:00", "body": "Staff meeting in the front office. Agenda attached to the invite.", "links": [], "attachment": "",
     "legit_why": "Expected internal reminder from a known domain, with no request for money, passwords or clicking."},
    {"id": "l3", "phish": False, "from_name": "Website Host", "from_addr": "billing@hosting-company.example", "subject": "Your receipt for October", "body": "Thanks for your payment. Your receipt is in your account area. We will never ask for your password by email.", "links": [], "attachment": "",
     "legit_why": "A receipt for something you actually pay for, with no link demanding action. Even so, go to the account by typing the address yourself."},
    {"id": "l4", "phish": False, "from_name": "Supplier (known)", "from_addr": "orders@usual-supplier.example", "subject": "Order 4471 shipped", "body": "Your order shipped today and should arrive Friday. Tracking is in your portal.", "links": [], "attachment": "",
     "legit_why": "You placed this order, the sender is your usual supplier, and the email asks nothing of you."},
    {"id": "l5", "phish": False, "from_name": "Password Manager", "from_addr": "noreply@password-manager.example", "subject": "New sign-in to your account", "body": "A sign-in from Windows in Las Vegas just happened. If this was you, no action needed. If not, open the app yourself and change your master password.", "links": [], "attachment": "",
     "legit_why": "Informational, no link to click, and the advice is to open the app yourself rather than follow a link."},
]


class PhishError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def deck(seed: int = 1, n: int = 8) -> dict:
    rnd = random.Random(seed)
    items = rnd.sample(MAILS, min(max(2, n), len(MAILS)))
    safe = [{k: m[k] for k in ("id", "from_name", "from_addr", "subject", "body", "links", "attachment")} for m in items]
    return {"seed": seed, "mails": safe, "how": "For each message decide: phish or real. Look at the sender's address, where links really go, any attachment, and whether it rushes or scares you.",
            "caution": "These are simple examples. Real phishing can be much more convincing, so when money, passwords or urgency are involved, verify by another route."}


def grade(answers: dict) -> dict:
    by = {m["id"]: m for m in MAILS}
    if not answers:
        raise PhishError("Answer at least one message.")
    res, right = [], 0
    for mid, a in answers.items():
        m = by.get(mid)
        if not m:
            raise PhishError(f"Unknown message {mid}.")
        if a not in ("phish", "real"):
            raise PhishError("Each answer must be phish or real.")
        ok = (a == "phish") == m["phish"]
        right += ok
        res.append({"id": mid, "your_answer": a, "correct": ok, "was": "phish" if m["phish"] else "real", "explain": m.get("tells") or [m["legit_why"]]})
    return {"score": right, "of": len(res), "results": res, "says": f"{right} of {len(res)} right.", "habit": "Check the sender address, hover to see where a link really goes, be suspicious of attachments you did not expect, and treat urgency or fear as a warning sign. When in doubt, verify by phone using a number you already have."}
