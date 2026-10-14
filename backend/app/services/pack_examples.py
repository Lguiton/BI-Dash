"""Made-up example values so every tool shows a real result on first click. Replace them with your own."""
from __future__ import annotations

from app.services.fieldpacks import PACKS

EX = {
    ("biz", "swot"): {"name": "Corner repair shop", "s": "Fast turnaround: 80% of repairs done within 2 days\nLoyal local customers with 40% repeat business", "w": "Only one technician, so a sick day stops work\nNo online booking: 30% of calls go to voicemail", "o": "Two nearby shops closed this year\nBusinesses want monthly support plans", "t": "A large chain opened 3 miles away\nParts prices rose 12% this year"},
    ("biz", "okr"): {"objective": "Make repeat business the core of the shop", "krs": "Raise repeat customers from 40% to 55% by December\nSign 10 monthly support plans by December\nCut voicemail-only enquiries from 30% to 10%"},
    ("biz", "sop"): {"title": "Open a repair ticket", "owner": "Front desk lead", "purpose": "Every device gets logged the same way so nothing is lost or disputed.", "steps": "Greet the customer and ask what is wrong\nRecord make, model and the symptoms\nPhotograph the device and note existing damage\nGet the passcode or note that none was given\nGive a written estimate and get a signature\nPrint the ticket and attach it to the device", "tools": "Ticket form\nCamera"},
    ("itpm", "evm"): {"bac": "100000", "pv": "40000", "ev": "30000", "ac": "45000"},
    ("itpm", "change"): {"project": "Office network upgrade", "title": "Add Wi-Fi to the warehouse", "why": "Pickers need scanners that work on the floor.", "cost": "$4,200", "days": "6", "risk": "Needs a second switch; installation must happen outside shift hours.", "requester": "Operations manager"},
    ("itpm", "golive"): {"system": "New accounting system", "date": "2026-11-16", "rollback_owner": "Finance director", "users": "Finance team (6 people)"},
    ("mkt", "campaign"): {"spend": "1000", "impressions": "100000", "clicks": "1500", "conversions": "30", "revenue": "3000"},
    ("mkt", "calendar"): {"topics": "Customer story\nBehind the scenes\nTip of the week\nOffer", "start": ""},
    ("mkt", "utm"): {"url": "example.com/offer", "source": "instagram", "medium": "social", "campaign": "fall sale", "content": "story-1"},
    ("revops", "econ"): {"arpa": "100", "cac": "600"},
    ("ux", "usability"): {"product": "Online booking page"},
    ("cds", "phi"): {"text": "Patient: Jane Example seen 03/04/2026\nMRN 123456\nCall 702-555-0100 or jane@example.com\nLives at 12 Maple Street"},
    ("cds", "table1"): {"csv": "age,sex,smoker,group\n61,M,yes,treated\n70,F,no,treated\n55,M,no,treated\n67,F,yes,treated\n58,M,yes,control\n74,F,no,control\n80,M,yes,control\n66,F,no,control", "group": "group"},
    ("cds", "diag"): {"tp": "90", "fp": "30", "fn": "10", "tn": "170", "prev": "5"},
    ("hana", "rate"): {"events": "12", "pop": "8000", "ref": "1.0"},
    ("hana", "smr"): {"obs": "25", "exp": "18"},
    ("hana", "los"): {"days": "3 5 7 4 30 6 8 5 9 4 12 6", "threshold": "14"},
    ("hana", "prop"): {"x": "18", "n": "120"},
    ("hbi", "kpi"): {"a": "5000", "b": "1600"},
    ("hinf", "hl7"): {"msg": "MSH|^~\\&|EHR|FAC|LAB|FAC|20260101120000||ADT^A01|MSG0001|P|2.5\rEVN|A01|20260101120000\rPID|1||000111^^^FAC||EXAMPLE^JANE||19800101|F\rPV1|1|I|2W^201^A"},
    ("hinf", "fhir"): {"json": "{\n  \"resourceType\": \"Observation\",\n  \"id\": \"example\",\n  \"status\": \"final\",\n  \"code\": {\"coding\": [{\"system\": \"http://loinc.org\", \"code\": \"8867-4\", \"display\": \"Heart rate\"}]},\n  \"subject\": {\"reference\": \"Patient/example\"},\n  \"effectiveDateTime\": \"2026-03-01T10:00:00Z\",\n  \"valueQuantity\": {\"value\": 72, \"unit\": \"beats/minute\"}\n}"},
    ("hinf", "codes"): {"codes": "E11.9\nI10\nZ99.89\nnot-a-code"},
    ("hinf", "spec"): {"sender": "Electronic health record", "receiver": "Lab system", "events": "Order placed\nOrder cancelled\nResult ready"},
    ("stat", "ci"): {"data": "5.1 6.2 5.8 7.0 6.4 5.5 6.1 5.9", "x": "12", "n": "40"},
    ("stat", "power"): {"a": "5", "b": "10"},
    ("gen", "hwe"): {"aa": "50", "ab": "40", "bb": "10"},
    ("gen", "assoc"): {"ca": "40", "cn": "60", "ka": "20", "kn": "80"},
    ("sci", "effect"): {"m1": "10", "s1": "2", "n1": "30", "m2": "8", "s2": "2", "n2": "30"},
    ("sci", "protocol"): {"title": "Walking programme and blood pressure", "population": "Adults aged 50 to 70 with mildly raised blood pressure", "intervention": "30-minute guided walk, 4 days a week for 12 weeks", "comparison": "Usual activity", "outcome": "Change in systolic blood pressure at 12 weeks"},
    ("sci", "cite"): {"authors": "Smith, John A.\nLee, Mary", "year": "2020", "title": "A study of useful things", "journal": "Journal of Examples", "volume": "12", "issue": "3", "pages": "45-67", "doi": "10.1000/abc123"},
    ("sci", "power"): {"a": "5", "b": "10"},
    ("devops", "dora"): {"deploys": "3", "lead": "48", "cfr": "20", "mttr": "6"},
    ("devops", "dockercheck"): {"text": "FROM python\nENV API_KEY=abc12345\nRUN curl http://example.com/install | sh\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"python\", \"app.py\"]"},
    ("devsecops", "secrets"): {"text": "aws_key = AKIA" + "ABCDEFGHIJKLMNOP\npassword = \"correct-horse-battery\"\nprint('hello')"},
    ("devsecops", "pipeline"): {"text": "on:\n  pull_request_target:\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: someone/some-action@main\n      - run: echo \"${{ github.event.pull_request.title }}\""},
    ("devsecops", "deps"): {"text": "flask>=2.0\nrequests==2.31.0\nnumpy\npandas~=2.1"},
    ("devsecops", "dockercheck"): {"text": "FROM python:3.12-slim\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY . .\nCMD [\"python\", \"app.py\"]"},
}

for (pid, tid), vals in EX.items():
    for i in PACKS[pid]["tools"][tid]["inputs"]:
        if i["name"] in vals and not i["default"]:
            i["default"] = vals[i["name"]]
