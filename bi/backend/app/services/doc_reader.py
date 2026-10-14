"""Document reader: turn OCR/pasted text of an invoice, receipt or bank statement into
fields, run the checks a person would, and export CSV.  No OCR engine is bundled -
paste text from any OCR tool.  Everything is regex rules, so it shows its evidence."""
import csv
import io
import re

MAX_CHARS = 20000
MONEY = r"[-(]?\$?\s?\d{1,3}(?:[,]\d{3})*(?:\.\d{1,2})?\)?|[-(]?\$?\s?\d+(?:\.\d{1,2})?\)?"


class DocError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _num(s: str) -> float | None:
    t = s.strip()
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = re.sub(r"[^\d.]", "", t)
    if not t or t == ".":
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _amounts(line: str) -> list[float]:
    out = []
    for m in re.finditer(r"(?<![\w/.-])(-?\(?\$?\s?\d[\d,]*\.\d{2}\)?)(?![\w/])", line):
        v = _num(m.group(1))
        if v is not None:
            out.append(v)
    return out


DATE_RE = re.compile(r"\b(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})\b|\b([A-Z][a-z]{2,8})\.? (\d{1,2}),? (\d{4})\b|\b(\d{1,2}) ([A-Z][a-z]{2,8})\.? (\d{4})\b")
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def _date(m) -> dict:
    raw = m.group(0)
    if m.group(1):
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if len(m.group(1)) == 4:
            y, mo, d, amb = a, b, c, False
        else:
            y = c + 2000 if c < 100 else c
            if a > 12:
                d, mo, amb = a, b, False
            elif b > 12:
                mo, d, amb = a, b, False
            else:
                mo, d, amb = a, b, a != b
    elif m.group(4):
        mo, d, y, amb = MONTHS.get(m.group(4)[:3].lower(), 0), int(m.group(5)), int(m.group(6)), False
    else:
        d, mo, y, amb = int(m.group(7)), MONTHS.get(m.group(8)[:3].lower(), 0), int(m.group(9)), False
    ok = 1 <= mo <= 12 and 1 <= d <= 31
    return {"raw": raw, "iso": f"{y:04d}-{mo:02d}-{d:02d}" if ok else None, "ambiguous": bool(amb and ok)}


def _first(rx: str, text: str, flags=re.I):
    m = re.search(rx, text, flags)
    return m.group(1).strip() if m else None


def _label_amount(text: str, labels: str) -> float | None:
    for line in text.splitlines():
        if re.search(rf"^\W*(?:{labels})\b", line.strip(), re.I):
            a = _amounts(line)
            if a:
                return a[-1]
    return None


def detect_kind(text: str) -> str:
    t = text.lower()
    if re.search(r"statement|opening balance|closing balance|available balance", t):
        return "statement"
    if re.search(r"invoice|bill to|due date|purchase order|\bpo\b", t):
        return "invoice"
    return "receipt"


def _items(text: str) -> list[dict]:
    items = []
    for line in text.splitlines():
        s = line.strip()
        if not s or re.search(r"^\W*(sub\s*total|total|tax|vat|gst|balance|amount due|discount|shipping|change|cash|visa|mastercard|tip)\b", s, re.I):
            continue
        a = _amounts(s)
        if not a:
            continue
        m = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*[x@]\s*\$?(\d[\d,]*\.\d{2})\s+\$?(\d[\d,]*\.\d{2})\s*$", s)
        if m:
            items.append({"description": m.group(1), "qty": float(m.group(2)), "unit_price": _num(m.group(3)), "amount": _num(m.group(4))})
            continue
        desc = re.sub(r"\s*\$?-?\(?\d[\d,]*\.\d{2}\)?\s*$", "", s).strip()
        if desc and not DATE_RE.fullmatch(desc) and re.search(r"[A-Za-z]", desc) and not re.search(r"invoice|date|phone|tel|www|@", desc, re.I):
            items.append({"description": desc, "qty": None, "unit_price": None, "amount": a[-1]})
    return items


def _check(name, ok, detail):
    return {"check": name, "ok": ok, "detail": detail}


def _statement(text: str) -> dict:
    rows, checks, warns = [], [], []
    opening = _label_amount(text, r"opening balance|previous balance|beginning balance")
    closing = _label_amount(text, r"closing balance|ending balance|new balance")
    for line in text.splitlines():
        m = DATE_RE.search(line)
        if not m or re.search(r"opening|closing|balance forward", line, re.I):
            continue
        a = _amounts(line[m.end():])
        if not a:
            continue
        desc = re.sub(r"\s*-?\(?\$?\d[\d,]*\.\d{2}\)?", "", line[m.end():]).strip(" -|:")
        d = _date(m)
        row = {"date": d["iso"], "date_raw": d["raw"], "description": desc, "amount": a[0] if len(a) >= 1 else None, "balance": a[1] if len(a) >= 2 else None}
        if d["ambiguous"]:
            warns.append(f"Date {d['raw']} could be day/month or month/day - confirm the statement's format.")
        rows.append(row)
    if not rows:
        raise DocError("No dated transaction lines found. Expect lines like '03/14/2026  Coffee shop  -4.50  1,204.10'.")
    net = round(sum(r["amount"] for r in rows), 2)
    if opening is not None and closing is not None:
        checks.append(_check("opening + transactions = closing", abs(opening + net - closing) < 0.01, f"{opening} + {net} = {round(opening + net, 2)} vs closing {closing}"))
    else:
        warns.append("Opening/closing balance not found, so the roll-forward check was skipped.")
    prev = opening
    bad = 0
    for r in rows:
        if r["balance"] is not None and prev is not None and abs(prev + r["amount"] - r["balance"]) >= 0.01:
            bad += 1
        if r["balance"] is not None:
            prev = r["balance"]
    if any(r["balance"] is not None for r in rows):
        checks.append(_check("running balance consistent", bad == 0, "every row follows from the one above" if bad == 0 else f"{bad} row(s) where balance does not follow - a missed or mis-read line"))
    return {"fields": {"opening_balance": opening, "closing_balance": closing, "net_movement": net, "transactions": len(rows)}, "rows": rows, "checks": checks, "warnings": warns}


def parse(text: str, kind: str = "auto", seen: list[str] | None = None) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise DocError("Paste the text of the document first.")
    if len(text) > MAX_CHARS:
        raise DocError(f"Text is over {MAX_CHARS} characters.", 413)
    kind = (kind or "auto").lower()
    if kind not in ("auto", "invoice", "receipt", "statement"):
        raise DocError("kind must be auto, invoice, receipt or statement.")
    used = detect_kind(text) if kind == "auto" else kind
    base = {"kind": used, "detected": kind == "auto"}
    if used == "statement":
        return base | _statement(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    vendor = next((ln for ln in lines if re.search(r"[A-Za-z]{3}", ln) and not re.search(r"invoice|receipt|bill to|date|total|page", ln, re.I)), None)
    number = _first(r"(?:invoice|inv|receipt|order)\s*(?:no\.?|number|#|:)\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{2,})", text)
    dates = [_date(m) for m in DATE_RE.finditer(text)]
    due = None
    for ln in lines:
        if re.search(r"due", ln, re.I):
            m = DATE_RE.search(ln)
            if m:
                due = _date(m)
                break
    first_date = next((d for d in dates if due is None or d["raw"] != due["raw"]), None)
    total = _label_amount(text, r"grand total|total due|amount due|balance due|total")
    sub = _label_amount(text, r"sub\s*-?total")
    tax = _label_amount(text, r"tax|vat|gst|sales tax")
    disc = _label_amount(text, r"discount")
    cur = "USD" if "$" in text else ("EUR" if "€" in text else ("GBP" if "£" in text else None))
    items = _items(text)
    checks, warns = [], []
    if sub is not None and tax is not None and total is not None:
        exp = round(sub + tax - (abs(disc) if disc else 0), 2)
        checks.append(_check("subtotal + tax = total", abs(exp - total) < 0.01, f"{sub} + {tax}{' - ' + str(abs(disc)) if disc else ''} = {exp} vs total {total}"))
    elif total is None:
        warns.append("No total found - the most important field. Check the OCR output near the bottom of the page.")
    li = [i["amount"] for i in items if i["amount"] is not None]
    if li and sub is not None:
        checks.append(_check("line items add up to subtotal", abs(sum(li) - sub) < 0.01, f"lines sum to {round(sum(li), 2)} vs subtotal {sub}"))
    for i in items:
        if i["qty"] and i["unit_price"] is not None and abs(i["qty"] * i["unit_price"] - i["amount"]) >= 0.01:
            checks.append(_check(f"qty x price: {i['description'][:30]}", False, f"{i['qty']} x {i['unit_price']} = {round(i['qty'] * i['unit_price'], 2)} but line says {i['amount']}"))
    if sub is not None and tax is not None and sub > 0 and not 0 <= tax / sub <= 0.3:
        warns.append(f"Tax is {round(100 * tax / sub, 1)}% of subtotal - unusual; OCR may have dropped a digit.")
    if first_date and first_date["ambiguous"]:
        warns.append(f"Date {first_date['raw']} could be day/month or month/day - confirm before posting.")
    if first_date and first_date["iso"] is None:
        warns.append(f"Date {first_date['raw']} is not a real date - likely an OCR error.")
    if re.search(r"(?<=\d)[OoIl](?=\d)|(?<=\d)[Ss](?=\d)", text):
        warns.append("Letters sit between digits (O/I/l/S for 0/1/5) - classic OCR confusion; check the numbers.")
    if not number and used == "invoice":
        warns.append("No invoice number found.")
    key = f"{(vendor or '').lower()}|{(number or '').lower()}|{total}"
    dup = bool(seen and key in [s.lower() for s in seen])
    if dup:
        warns.append("Looks like a duplicate of one already entered (same vendor, number and total).")
    return base | {
        "fields": {"vendor": vendor, "number": number, "date": first_date["iso"] if first_date else None, "due_date": due["iso"] if due else None,
                   "currency": cur, "subtotal": sub, "tax": tax, "discount": disc, "total": total},
        "rows": items, "checks": checks, "warnings": warns, "duplicate_key": key, "duplicate": dup,
        "needs_review": bool(warns) or any(not c["ok"] for c in checks),
    }


def _safe(v):
    """Neutralise spreadsheet formulas in text cells (CSV injection)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def to_csv(result: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    rows = result.get("rows") or []
    if rows:
        cols = list(rows[0])
        w.writerow(cols)
        for r in rows:
            w.writerow([_safe(r.get(c)) if isinstance(r.get(c), str) else r.get(c) for c in cols])
    else:
        w.writerow(["field", "value"])
        for k, v in (result.get("fields") or {}).items():
            w.writerow([k, _safe(v)])
    return buf.getvalue()


SLIPS = [
    "OCR output is a draft, not a record: always run the arithmetic checks before it reaches a ledger.",
    "Dates like 03/04/2026 are ambiguous - the reader flags them rather than guessing.",
    "An 'accuracy' figure on a vendor page is measured on their test set; measure it on your own 20 documents.",
]
NOT_BUILT = ["The OCR engine itself (image/PDF to text) - run Tesseract or a cloud OCR and paste the text here.", "Layout or table-structure detection, handwriting and signature recognition."]

SAMPLES = {
    "invoice": "Northwind Supplies Ltd\nInvoice No: INV-20417\nInvoice Date: 2026-03-14\nDue Date: 2026-04-13\nBill To: Acme Corp\n\nPaper A4 box  10 x 24.50  245.00\nToner cartridge  2 x 89.99  179.98\nDelivery  35.00\n\nSubtotal 459.98\nTax 36.80\nTotal Due 496.78\n",
    "statement": "Acme Bank Statement\nOpening balance 1,000.00\n03/01/2026 Salary 2,500.00 3,500.00\n03/03/2026 Rent -1,200.00 2,300.00\n03/09/2026 Groceries -86.40 2,213.60\nClosing balance 2,213.60\n",
}
