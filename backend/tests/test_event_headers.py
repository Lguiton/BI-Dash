from fastapi.testclient import TestClient

from app.main import app
from app.services import itlab

CSV = "level,date_and_time,source,event_id,task_category\nInformation,10/15/2026 8:49:36 PM,Service Control Manager,7036,None\nError,10/15/2026 8:50:00 PM,Microsoft-Windows-Kernel-Power,41,(63)\nError,10/15/2026 8:51:00 PM,Disk,7,None\n"


def test_underscore_event_id_header_is_read():
    r = itlab.read_events(CSV)
    assert r["events"] == 3 and {t["id"] for t in r["table"]} == {7036, 41, 7}


def test_business_importer_points_event_logs_to_it(client=None):
    c = TestClient(app)
    r = c.post("/api/ingest/csv?mode=append", files={"file": ("eventlogs.csv", CSV.encode(), "text/csv")})
    assert r.status_code >= 400 and "event log" in str(r.json()).lower()
