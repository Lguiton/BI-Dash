"""Exercise 1 - structured output: turn messy text into validated data.

    python 01_structured_output.py

Models say plausible things; your program needs *valid* things. The pattern:
  ask for JSON -> parse -> validate with a schema -> on failure, feed the error back and retry (bounded).
"""
import json
import re
from pydantic import BaseModel, Field, ValidationError

from llm import complete, live, offline

SYSTEM = "You extract fields from operations notes. Reply with ONLY a JSON object, no prose."


class Ticket(BaseModel):
    entity: str
    issue: str
    severity: int = Field(ge=1, le=5)
    revenue_at_risk_usd: float = Field(ge=0)


NOTES = [
    "Zone West Central: conveyor jam since 9am, sev 4, about $1,200 of revenue stuck.",
    "ENT-07 reports a late truck, minor (sev 2). Nothing lost yet.",
]


@offline(r"NOTE: (.*?)\nEND")
def _stub(m, system):
    note = m.group(1)
    sev = re.search(r"sev (\d)", note)
    money = re.search(r"\$([\d,]+)", note)
    code = re.search(r"ENT-\d+", note)
    ent = code.group(0) if code else note.split(":")[0].strip() if ":" in note else "unknown"
    return json.dumps({"entity": ent,
                       "issue": note.split(",")[0][:60],
                       "severity": int(sev.group(1)) if sev else 3,
                       "revenue_at_risk_usd": float(money.group(1).replace(",", "")) if money else 0})


def extract(note: str, max_tries: int = 3) -> Ticket:
    prompt = f"Schema: {json.dumps(Ticket.model_json_schema()['properties'])}\nNOTE: {note}\nEND"
    last_error = ""
    for attempt in range(1, max_tries + 1):
        raw = complete(SYSTEM, prompt + (f"\nYour previous answer was invalid: {last_error}. Fix it." if last_error else ""))
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()  # models love code fences
        try:
            return Ticket.model_validate_json(raw)
        except ValidationError as e:
            last_error = str(e).splitlines()[0]
            print(f"  attempt {attempt} rejected: {last_error}")
    raise ValueError(f"no valid answer after {max_tries} tries")


if __name__ == "__main__":
    print("mode:", "live Claude" if live() else "offline stub")
    for n in NOTES:
        print(extract(n).model_dump())
    print("\nYour turn: add a field (e.g. `needs_escalation: bool`), teach the stub or prompt to fill it, and add a test.")
