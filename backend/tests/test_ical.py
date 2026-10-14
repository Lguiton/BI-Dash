from datetime import datetime, timezone

import pytest

from app.services import ical, sources

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
ICS = """BEGIN:VCALENDAR
X-WR-TIMEZONE:America/Los_Angeles
BEGIN:VEVENT
UID:a1
DTSTART;TZID=America/Los_Angeles:20261014T090000
DTEND;TZID=America/Los_Angeles:20261014T103000
SUMMARY:Instacart batch\\, Costco
LOCATION:Las Vegas
END:VEVENT
BEGIN:VEVENT
UID:w1
DTSTART;TZID=America/Los_Angeles:20261005T180000
DTEND;TZID=America/Los_Angeles:20261005T190000
RRULE:FREQ=WEEKLY;COUNT=6
EXDATE;TZID=America/Los_Angeles:20261019T180000
SUMMARY:Class
END:VEVENT
BEGIN:VEVENT
UID:w1
RECURRENCE-ID;TZID=America/Los_Angeles:20261026T180000
DTSTART;TZID=America/Los_Angeles:20261026T200000
DTEND;TZID=America/Los_Angeles:20261026T210000
SUMMARY:Class (moved)
END:VEVENT
BEGIN:VEVENT
UID:d1
DTSTART;VALUE=DATE:20261020
DTEND;VALUE=DATE:20261021
SUMMARY:Car registration due
END:VEVENT
BEGIN:VEVENT
UID:c1
DTSTART:20261015T170000Z
DTEND:20261015T180000Z
STATUS:CANCELLED
SUMMARY:Cancelled thing
END:VEVENT
BEGIN:VEVENT
UID:old
DTSTART:20250101T170000Z
DTEND:20250101T180000Z
SUMMARY:Way back
END:VEVENT
END:VCALENDAR
"""


def rows():
    return {tuple(r[:2]): r for r in ical.parse(ICS, now=NOW)}


def test_events_expand_and_filter():
    r = rows()
    titles = [x[0] for x in r.values()]
    assert "Instacart batch, Costco" in titles                       # escape handled
    assert titles.count("Class") == 4                                # Oct 5, 12, Nov 2, 9 (19 excluded, 26 moved)
    assert "Class (moved)" in titles
    assert ("Class", "2026-10-19 18:00") not in r                    # EXDATE
    assert ("Class", "2026-10-26 18:00") not in r                    # replaced by override
    assert "Cancelled thing" not in titles and "Way back" not in titles
    inst = r[("Instacart batch, Costco", "2026-10-14 09:00")]
    assert inst[3] == "no" and inst[4] == "1.5" and inst[5] == "Las Vegas"
    day = r[("Car registration due", "2026-10-20")]
    assert day[3] == "yes" and day[4] == ""


def test_not_a_calendar_and_env_rules(monkeypatch):
    with pytest.raises(ical.IcalError):
        ical.parse("<html>nope</html>")
    with pytest.raises(sources.SourceError):
        sources.validate_config("ical", {"url_env": "https://secret.example/x.ics"})   # a link, not a variable name
    assert sources.validate_config("ical", {"url_env": "GCAL_URL"})["future_days"] == 180
    monkeypatch.delenv("GCAL_URL", raising=False)
    with pytest.raises(ical.IcalError, match="not set"):
        ical.fetch({"url_env": "GCAL_URL"})
    monkeypatch.setenv("GCAL_URL", "http://calendar.example/x.ics")
    with pytest.raises(ical.IcalError, match="https"):
        ical.fetch({"url_env": "GCAL_URL"})


def test_config_never_holds_the_link():
    cfg = sources.validate_config("ical", {"url_env": "GCAL_URL", "url": "https://calendar.google.com/secret.ics"})
    assert "url" not in cfg
