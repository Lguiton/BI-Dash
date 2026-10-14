"""One-click client report for a business dashboard: plain-English summary, KPI table, trend, breakdowns and next actions, as HTML or PDF.

The wording is rule-based (no AI, nothing leaves your computer): it reads the same numbers the dashboard shows. In Practice mode the report is stamped
SAMPLE DATA so a practice report can never be mistaken for a client deliverable."""
from __future__ import annotations

import html
import io
import re
from datetime import date

from app.services import biz_packs, workspaces

UNIT = {"usd": lambda v: f"${v:,.2f}" if abs(v) < 100 else f"${v:,.0f}", "pct": lambda v: f"{v:.1f}%", "count": lambda v: f"{v:,.0f}", "num": lambda v: f"{v:,.2f}"}


def _fmt(unit: str, v) -> str:
    return "n/a" if v is None else UNIT.get(unit, UNIT["num"])(float(v))


def _clean(s: str | None, limit: int = 80) -> str:
    return re.sub(r"[\x00-\x1f]", " ", (s or "")).strip()[:limit]


def build(pid: str, days: int = 30, client: str = "", prepared_by: str = "") -> dict:
    if days not in (0, 7, 14, 30, 60, 90, 180, 365):
        raise biz_packs.PackError("Choose 7, 14, 30, 60, 90, 180 or 365 days, or 0 for all data.")
    d = biz_packs.dashboard(pid, days)
    period = "all data" if days == 0 else f"the last {days} days"
    moved = [k for k in d["kpis"] if k["change_pct"] is not None]
    wins = sorted([k for k in moved if k["good"]], key=lambda k: -abs(k["change_pct"]))[:2]
    risks = sorted([k for k in moved if k["good"] is False], key=lambda k: -abs(k["change_pct"]))[:3]
    summary = []
    if not moved:
        summary.append(f"This report covers {period} ({d['records']:,} records). There is not yet an earlier period of the same length to compare against, so it shows levels, not changes.")
    else:
        summary.append(f"This report covers {period} ({d['records']:,} records) compared with the {'' if days == 0 else str(days) + ' days '}before.")
        for k in wins:
            summary.append(f"Good news: {k['label']} is {_fmt(k['unit'], k['value'])}, {'up' if k['change_pct'] > 0 else 'down'} {abs(k['change_pct']):.1f}% (better).")
        for k in risks:
            summary.append(f"Watch: {k['label']} is {_fmt(k['unit'], k['value'])}, {'up' if k['change_pct'] > 0 else 'down'} {abs(k['change_pct']):.1f}% (worse).")
        if not wins and not risks:
            summary.append("No measure moved enough to call good or bad.")
    actions = []
    dims = [b for b in d["breakdowns"] if b["rows"]]
    for k in risks:
        where = f" Start with the {dims[0]['dim'].replace('_', ' ')} breakdown below, where '{dims[0]['rows'][0]['name']}' is the largest group." if dims else ""
        actions.append(f"Find out why {k['label']} got worse.{where}")
    if wins:
        actions.append(f"Protect what is working: note what changed behind {wins[0]['label']} so it can be repeated.")
    if not actions:
        actions.append("Keep the data current (weekly is enough) so changes show up early.")
    actions.append("Re-run this report next period and compare.")
    sample = workspaces.active() != "real"
    return {**d, "client": _clean(client), "prepared_by": _clean(prepared_by), "period": period, "summary": summary, "actions": actions[:4], "sample": sample, "generated": date.today().isoformat(),
            "caveat": "Figures come from the data loaded into this dashboard. A change shows that two numbers moved together, not why; check the cause before acting."}


def _spark(trend: list[dict], w=520, h=90) -> str:
    vals = [t["value"] for t in trend if t["value"] is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = " ".join(f"{4 + i * (w - 8) / (len(vals) - 1):.1f},{h - 6 - (v - lo) / span * (h - 12):.1f}" for i, v in enumerate(vals))
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" aria-label="Trend"><polyline fill="none" stroke="#0f6b4a" stroke-width="2" points="{pts}"/></svg>'


def _chg(k: dict) -> str:
    return "n/a" if k["change_pct"] is None else f"{k['change_pct']:+.1f}%"


def to_html(r: dict) -> str:
    e = html.escape
    rows = "".join(f"<tr><td>{e(k['label'])}</td><td class=n>{e(_fmt(k['unit'], k['value']))}</td><td class=n>{e(_fmt(k['unit'], k['previous']))}</td>"
                   f"<td class='n {'good' if k['good'] else 'bad' if k['good'] is False else ''}'>{_chg(k)}</td></tr>" for k in r["kpis"])
    br = "".join(f"<h3>{e(b['dim'].replace('_', ' ').title())}</h3><table>" + "".join(f"<tr><td>{e(str(x['name']))}</td><td class=n>{e(_fmt('num', x['value']))}</td></tr>" for x in b["rows"][:8]) + "</table>" for b in r["breakdowns"] if b["rows"])
    who = " · ".join(x for x in (f"For {e(r['client'])}" if r["client"] else "", f"Prepared by {e(r['prepared_by'])}" if r["prepared_by"] else "", e(r["generated"])) if x)
    banner = '<p class=sample>SAMPLE DATA: this report came from the Practice workspace and is not a client deliverable.</p>' if r["sample"] else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(r['title'])} report</title>
<style>body{{font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#1b1f1d}}h1{{margin:.2rem 0}}h2{{margin-top:1.6rem;border-bottom:2px solid #0f6b4a;padding-bottom:.2rem}}
h3{{margin:1rem 0 .2rem}}table{{border-collapse:collapse;width:100%;margin:.4rem 0}}td,th{{padding:.35rem .5rem;border-bottom:1px solid #ddd;text-align:left}}.n{{text-align:right;font-variant-numeric:tabular-nums}}
.good{{color:#0f6b4a;font-weight:600}}.bad{{color:#b3261e;font-weight:600}}.sub{{color:#555}}.sample{{background:#fff3cd;border:1px solid #e0b000;padding:.5rem .8rem;font-weight:600}}
.cav{{color:#555;font-size:.85rem;margin-top:2rem}}@media print{{body{{margin:0}}}}</style></head><body>
{banner}<p class=sub>{e(r['industry'])} · {e(r['dept'])}</p><h1>{e(r['title'])}</h1><p class=sub>{who}</p>
<h2>Summary</h2>{''.join(f'<p>{e(s)}</p>' for s in r['summary'])}
<h2>Key numbers</h2><table><tr><th>Measure</th><th class=n>This period</th><th class=n>Before</th><th class=n>Change</th></tr>{rows}</table>
<h2>{e(r['trend_label'])} over time</h2>{_spark(r['trend'])}
<h2>Where it comes from</h2>{br}
<h2>Next actions</h2><ol>{''.join(f'<li>{e(a)}</li>' for a in r['actions'])}</ol>
<p class=cav>{e(r['caveat'])}</p></body></html>"""


def to_pdf(r: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.graphics.shapes import Drawing, PolyLine
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as x
    st = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch, title=r["title"], author=r["prepared_by"] or "BI Dashboard")
    f: list = []
    if r["sample"]:
        f += [Paragraph("<b>SAMPLE DATA: Practice workspace, not a client deliverable.</b>", st["Normal"]), Spacer(1, 6)]
    f += [Paragraph(x(f"{r['industry']} · {r['dept']}"), st["Normal"]), Paragraph(x(r["title"]), st["Title"])]
    f.append(Paragraph(x(" · ".join(v for v in (f"For {r['client']}" if r["client"] else "", f"Prepared by {r['prepared_by']}" if r["prepared_by"] else "", r["generated"]) if v)), st["Normal"]))
    f += [Spacer(1, 10), Paragraph("Summary", st["Heading2"])] + [Paragraph(x(s), st["Normal"]) for s in r["summary"]]
    data = [["Measure", "This period", "Before", "Change"]] + [[k["label"], _fmt(k["unit"], k["value"]), _fmt(k["unit"], k["previous"]), "n/a" if k["change_pct"] is None else f"{k['change_pct']:+.1f}%"] for k in r["kpis"]]
    t = Table(data, colWidths=[2.6 * inch, 1.5 * inch, 1.4 * inch, 1.0 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6b4a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    f += [Spacer(1, 8), Paragraph("Key numbers", st["Heading2"]), t]
    vals = [v["value"] for v in r["trend"] if v["value"] is not None]
    if len(vals) > 1:
        w, h = 6.2 * inch, 1.1 * inch
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1
        dr = Drawing(w, h)
        dr.add(PolyLine([c for i, v in enumerate(vals) for c in (4 + i * (w - 8) / (len(vals) - 1), 4 + (v - lo) / span * (h - 8))], strokeColor=colors.HexColor("#0f6b4a"), strokeWidth=1.5))
        f += [Paragraph(x(f"{r['trend_label']} over time"), st["Heading2"]), dr]
    f.append(Paragraph("Where it comes from", st["Heading2"]))
    for b in r["breakdowns"]:
        if b["rows"]:
            tb = Table([[str(row["name"]), _fmt("num", row["value"])] for row in b["rows"][:8]], colWidths=[3.5 * inch, 1.5 * inch])
            tb.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
            f += [Paragraph(x(b["dim"].replace("_", " ").title()), st["Heading3"]), tb]
    f += [Paragraph("Next actions", st["Heading2"])] + [Paragraph(x(f"{i}. {a}"), st["Normal"]) for i, a in enumerate(r["actions"], 1)]
    f += [Spacer(1, 12), Paragraph(f"<font size=8 color='#555555'>{x(r['caveat'])}</font>", st["Normal"])]
    doc.build(f)
    return buf.getvalue()
