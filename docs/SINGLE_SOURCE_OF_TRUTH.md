# Single source of truth audits

From a manufacturing data-management whitepaper (five tactics). Systems analysis > Single source of truth.

## Built
- **Systems connectivity**: type each system, the information it holds (`*` marks the master) and where it sends data (`target:auto` or `target:manual`). Finds manual transfers, isolated systems, information held in several systems with no master, conflicting masters, spreadsheet-type systems, and the top integration priorities.
- **Metric audit**: metric, report, owner, decision, review habit. Finds metrics with no decision, owner, review or report; the same metric in several reports; too many metrics for one decision; and reports nobody reviews.
- **Document inventory**: finds copies of the same document, version words in titles (final, copy, v2, dates), missing owner, location or version, and stale reviews.
- **Search time cost**: people x searches x minutes x hourly cost, as your own estimate.
- **Key-person risk**: for each responsibility, primary, backup, documented, deadline. Shows who is exposed "if they left tomorrow", which deadlines within 90 days are at risk and who holds the most.
- Steps `sot-systems-metrics`, `sot-docs-people`, six questions, one agent note, two tool-map rows.

## Not built
Connecting real ERP/CRM/accounting systems or document management software; the independent review (tactic 5) is a person. n8n is a free way to practise integrations.

## Mistakes in the source
It is titled "5 steps to create a single source of truth" but none of the steps creates one (no system of record, ownership, quality rules or retirement of copies); tactic 5 is a sales pitch and the document ends with the author's own offer; no figures or sources for its claims; it omits access control, backup and data quality; "Information Organisational Chart" is undefined; conformity and compliance are blurred. See `SLIPS` in `info_audit.py`.

## Limits
The audits read typed rows. They cannot see your systems, and a clean result only means your list was clean.
