"""Real PDF files for the documents you hand to clients: an invoice, a job summary, a quote, the price list and a checklist.

Each one is built from the same data as its web page, so what you download matches what you see. Nothing is sent anywhere; the file is made on this computer.
Text from your notes is escaped before it goes into the PDF, so it can never act as formatting."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from app.services import clients


def _styles():
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Small", parent=ss["BodyText"], fontSize=8.5, leading=11, textColor="#555555"))
    ss.add(ParagraphStyle("Cell", parent=ss["BodyText"], fontSize=9, leading=11))
    ss.add(ParagraphStyle("CellR", parent=ss["BodyText"], fontSize=9, leading=11, alignment=2))
    return ss


def t(s) -> str:
    """Escape text for a PDF paragraph and keep line breaks."""
    return escape(str(s if s is not None else "")).replace("\n", "<br/>")


def build(title: str, blocks: list[tuple], subtitle: str = "", sample: bool = False) -> bytes:
    """blocks: ("h", text) ("p", text) ("small", text) ("kv", [(k, v)]) ("bullets", [text]) ("checks", [(text, done)])
    ("table", head, rows, right_cols, col_widths_in_inches or None) ("sp", points)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    ss = _styles()
    buf = io.BytesIO()
    business = ""
    try:
        business = clients._load()["settings"].get("business", "")
    except Exception:  # noqa: BLE001 - the PDF is still made without the business name
        pass

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(0.75 * inch, 0.5 * inch, (business or "")[:80])
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.7 * inch, bottomMargin=0.8 * inch, title=title[:100], author=business[:80])
    flow = []
    if sample:
        flow += [Paragraph("<b>SAMPLE:</b> made in the Practice workspace. Not a real document.", ss["BodyText"]), Spacer(1, 8)]
    flow.append(Paragraph(t(title), ss["Title"]))
    if subtitle:
        flow.append(Paragraph(t(subtitle), ss["Small"]))
        flow.append(Spacer(1, 8))
    for b in blocks:
        k = b[0]
        if k == "h":
            flow += [Spacer(1, 8), Paragraph(t(b[1]), ss["Heading3"])]
        elif k == "p":
            flow.append(Paragraph(t(b[1]), ss["BodyText"]))
        elif k == "small":
            flow.append(Paragraph(t(b[1]), ss["Small"]))
        elif k == "sp":
            flow.append(Spacer(1, b[1]))
        elif k == "kv":
            for key, val in b[1]:
                flow.append(Paragraph(f"<b>{t(key)}:</b> {t(val)}", ss["BodyText"]))
        elif k == "bullets":
            for x in b[1]:
                flow.append(Paragraph(f"&bull; {t(x)}", ss["BodyText"]))
        elif k == "checks":
            for text, done in b[1]:
                flow.append(Paragraph(f"{'[x]' if done else '[&nbsp;&nbsp;]'} {t(text)}", ss["BodyText"]))
        elif k == "table":
            head, rows, right, widths = b[1], b[2], set(b[3] or []), b[4] if len(b) > 4 else None
            data = [[Paragraph(f"<b>{t(h)}</b>", ss["CellR"] if i in right else ss["Cell"]) for i, h in enumerate(head)]]
            for r in rows:
                data.append([Paragraph(t(c), ss["CellR"] if i in right else ss["Cell"]) for i, c in enumerate(r)])
            tbl = Table(data, colWidths=[w * inch for w in widths] if widths else None, repeatRows=1)
            tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                                     ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            flow += [Spacer(1, 4), tbl, Spacer(1, 4)]
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ---------------------------------------------------------------- the documents
def invoice(iid: int) -> tuple[bytes, str]:
    d = clients._load()
    inv = clients._find(d, "invoices", iid)
    c = clients._find(d, "clients", inv["client_id"])
    s = d["settings"]
    rows = [(x["desc"], f"{x['qty']:g}", f"${x['rate']:,.2f}", f"${x['qty'] * x['rate']:,.2f}") for x in inv["lines"]]
    blocks: list[tuple] = []
    if s.get("business"):
        blocks.append(("p", s["business"]))
    blocks.append(("kv", [("Bill to", c["name"] + (f" ({c['contact']})" if c.get("contact") else "")), ("Issued", inv["issued"]), ("Due", inv["due"]), ("Status", inv["status"])]))
    blocks.append(("table", ["Description", "Qty", "Rate", "Amount"], rows, [1, 2, 3], [3.6, 0.7, 1.1, 1.1]))
    blocks.append(("p", f"Total: ${clients.inv_total(inv):,.2f}"))
    if inv.get("notes"):
        blocks.append(("p", inv["notes"]))
    if s.get("pay_to"):
        blocks.append(("kv", [("Pay to", s["pay_to"])]))
    return build(f"Invoice {inv['number']}", blocks, sample=clients.sample()), f"invoice-{inv['number']}.pdf"


def quote(q: dict) -> tuple[bytes, str]:
    per = lambda m: " / month" if m == "monthly" else " / session" if m == "hourly" else ""  # noqa: E731
    rows = [(f"{x['name']}" + (f" x {x['qty']}" if x["qty"] > 1 else ""), f"${x['low']:,.0f} to ${x['high']:,.0f}{per(x['model'])}") for x in q["lines"]]
    blocks: list[tuple] = [("table", ["Service", "Estimate"], rows, [1], [4.2, 2.3])]
    sub, tot = q["subtotal"], q["total"]
    blocks.append(("p", f"Subtotal: ${sub[0]:,.0f} to ${sub[1]:,.0f}" + (f", after {q['discount_pct']:g}% off:" if q["discount_pct"] else ". Total:") + f" ${tot[0]:,.0f} to ${tot[1]:,.0f}"))
    blocks.append(("small", q["note"]))
    title = "Quote" + (f" for {q['client']}" if q["client"] else "")
    return build(title, blocks), "quote.pdf"


def price_list(p: dict) -> tuple[bytes, str]:
    blocks: list[tuple] = [("small", f"Researched {p['date']}. Your price is set about 10 to 20 percent under the local market range. {p['note']}")]
    for g in p["groups"]:
        blocks.append(("h", g["group"]))
        blocks.append(("table", ["Service", "What you get", "Market", "Your price"], [(r["service"], r["gets"], r["market"], r["price"]) for r in g["rows"]], [], [1.5, 2.5, 1.5, 1.2]))
    return build("Henderson and Las Vegas price list", blocks), "price-list.pdf"


def checklist(tpl: dict, checked: set[str] | None = None, notes: str = "", job_title: str = "") -> tuple[bytes, str]:
    blocks: list[tuple] = [("small", tpl["when"])]
    for s in tpl["sections"]:
        blocks.append(("h", s["title"]))
        blocks.append(("checks", [(i["text"], checked is not None and i["id"] in checked) for i in s["items"]]))
    if notes:
        blocks += [("h", "Notes"), ("p", notes)]
    blocks.append(("sp", 6))
    blocks.append(("small", tpl["source"]))
    sub = f"Job: {job_title}" if job_title else "Blank checklist for printing"
    return build(tpl["title"], blocks, subtitle=sub), f"{tpl['id']}-checklist.pdf"


def fix_checklist(fix: dict) -> tuple[bytes, str]:
    """A fix from the fix log turned into a printable checklist: the steps that worked, then how to confirm and prevent."""
    sections = [{"title": "Steps that fixed it before", "items": [{"id": f"a{i}", "text": s} for i, s in enumerate(fix.get("steps") or [], 1)] or [{"id": "a1", "text": "(no steps were recorded)"}]},
                {"title": "Confirm it is fixed", "items": [{"id": "b1", "text": "Test the original problem again and watch it for a few minutes."}, {"id": "b2", "text": "Tell the client what you found and what you changed."}]}]
    if fix.get("prevention"):
        sections.append({"title": "Keep it from coming back", "items": [{"id": "c1", "text": fix["prevention"]}]})
    bits = [x for x in (f"Symptoms: {fix['symptoms']}" if fix.get("symptoms") else "", f"Usual cause: {fix['cause']}" if fix.get("cause") else "", f"Took about {fix['minutes']} minutes." if fix.get("minutes") else "") if x]
    tpl = {"id": f"fix-{fix['id']}", "title": f"Checklist: {fix['title']}", "when": " ".join(bits) or "From your fix log.", "sections": sections,
           "source": "Made from your own fix log entry. Change anything that doesn't fit this job."}
    return checklist(tpl, None, "", "")[0], f"fix-{fix['id']}-checklist.pdf"


def site_sheet(cid: int) -> tuple[bytes, str]:
    """A one-page sheet for a client: devices, network layout, recurring problems. Secrets were blanked when the notes were saved."""
    from app.services import clientnotes
    n = clientnotes.get(cid)
    blocks: list[tuple] = []
    if n["devices"]:
        blocks += [("h", "Devices"), ("table", ["Device", "Kind", "Where", "Model", "Address"], [[x["name"], x["kind"], x["where"], x["model"], x["address"]] for x in n["devices"]], [], None)]
    for key, head in (("network", "Network layout"), ("issues", "Problems that keep coming back"), ("notes", "Other notes")):
        if n[key]:
            blocks += [("h", head), ("p", n[key])]
    if not blocks:
        blocks = [("p", "No site notes saved yet.")]
    blocks += [("sp", 6), ("small", "No passwords are stored here. Keep real logins in a password manager.")]
    return build(f"Site sheet: {n['client']}", blocks, sample=n["sample"]), f"site-sheet-{cid}.pdf"
