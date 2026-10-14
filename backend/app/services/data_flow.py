"""Job scheduler and stream simulators for learning: a task graph with retries and limited workers, cron expressions,
and a small partitioned stream with consumer groups, windows and late events. Time is simulated; nothing is executed."""
from __future__ import annotations

import heapq
import re
import zlib
from datetime import datetime, timedelta

from app.services.data_dbt import DataLabError


def _lines(text, what, lo=1, hi=300):
    out = [l.split("#")[0].strip() for l in (text or "").splitlines()]
    out = [l for l in out if l]
    if len(out) < lo:
        raise DataLabError(f"Enter at least {lo} {what}.")
    if len(out) > hi:
        raise DataLabError(f"At most {hi} {what}s.")
    return out


# ------------------------------------------------------------ task graph
def dag(tasks: str, workers: int = 2) -> dict:
    if not isinstance(workers, int) or not 1 <= workers <= 16:
        raise DataLabError("Workers must be 1 to 16.")
    T = {}
    for l in _lines(tasks, "task line", 1, 60):
        p = [x.strip() for x in l.split("|")]
        if len(p) < 3 or len(p) > 6:
            raise DataLabError(f"Task '{l}': use 'name | depends_on (comma list or -) | minutes | fails_first (default 0) | retries (default 0) | retry_delay_min (default 1)'.")
        if not re.match(r"^[A-Za-z0-9_]{1,30}$", p[0]):
            raise DataLabError(f"'{p[0]}' is not a valid task name (letters, digits, underscore).")
        if p[0] in T:
            raise DataLabError(f"Task '{p[0]}' is listed twice.")
        try:
            dur = float(p[2])
            ff = int(p[3]) if len(p) > 3 and p[3] else 0
            rt = int(p[4]) if len(p) > 4 and p[4] else 0
            rd = float(p[5]) if len(p) > 5 and p[5] else 1.0
        except ValueError:
            raise DataLabError(f"Task '{l}': minutes, fails_first, retries and retry_delay must be numbers.") from None
        if dur <= 0 or ff < 0 or not 0 <= rt <= 10 or rd < 0:
            raise DataLabError(f"Task '{p[0]}': minutes must be above 0 and retries 0 to 10.")
        T[p[0]] = {"deps": [] if p[1] in ("-", "") else [d.strip() for d in p[1].split(",") if d.strip()], "dur": dur, "ff": ff, "rt": rt, "rd": rd}
    for n, t in T.items():
        for d in t["deps"]:
            if d not in T:
                raise DataLabError(f"Task '{n}' depends on '{d}', which is not defined.")
    # cycle check
    indeg = {n: len(t["deps"]) for n, t in T.items()}
    q = [n for n, d in indeg.items() if d == 0]
    seen = 0
    while q:
        u = q.pop()
        seen += 1
        for v, t in T.items():
            if u in t["deps"]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
    if seen != len(T):
        raise DataLabError("The tasks depend on each other in a circle: " + ", ".join(sorted(n for n, d in indeg.items() if d > 0)) + ".")
    # simulate with a worker pool
    state = {n: "waiting" for n in T}
    attempts = {n: 0 for n in T}
    done_at = {}
    events = []
    running: list[tuple[float, str]] = []
    ready_at = {n: 0.0 for n in T}
    free = workers
    now = 0.0
    segs = []
    guard = 0
    while True:
        guard += 1
        if guard > 5000:
            raise DataLabError("The simulation did not finish; check the tasks.")
        for n, t in T.items():
            if state[n] == "waiting" and any(state[d] in ("failed", "upstream_failed") for d in t["deps"]):
                state[n] = "upstream_failed"
        cand = sorted((ready_at[n], n) for n, t in T.items() if state[n] == "waiting" and all(state[d] == "success" for d in t["deps"]))
        started = False
        for ra, n in cand:
            if free > 0 and ra <= now:
                free -= 1
                attempts[n] += 1
                fail = attempts[n] <= T[n]["ff"]
                heapq.heappush(running, (now + T[n]["dur"], n))
                state[n] = "running"
                segs.append({"task": n, "attempt": attempts[n], "start": now, "end": now + T[n]["dur"], "result": "fail" if fail else "ok"})
                started = True
        if started:
            continue
        nexts = [r[0] for r in running] + [ra for ra, n in cand if ra > now]
        if not nexts:
            break
        now = min(nexts)
        while running and running[0][0] <= now:
            _, n = heapq.heappop(running)
            free += 1
            s = next(x for x in reversed(segs) if x["task"] == n)
            if s["result"] == "ok":
                state[n] = "success"
                done_at[n] = s["end"]
            elif attempts[n] <= T[n]["rt"]:
                state[n] = "waiting"
                ready_at[n] = now + T[n]["rd"]
                events.append(f"{n} failed at minute {now:g}; retry {attempts[n]} of {T[n]['rt']} after {T[n]['rd']:g} min.")
            else:
                state[n] = "failed"
                events.append(f"{n} failed at minute {now:g} with no retries left; everything after it is skipped.")
    # critical path (longest chain by plain duration)
    memo = {}

    def lp(n):
        if n not in memo:
            memo[n] = T[n]["dur"] + max((lp(d) for d in T[n]["deps"]), default=0)
        return memo[n]
    end = max(lp(n) for n in T)
    tail = max(T, key=lp)
    path = [tail]
    while T[path[-1]]["deps"]:
        path.append(max(T[path[-1]]["deps"], key=lp))
    total = max((s["end"] for s in segs), default=0.0)
    return {"workers": workers, "status": {n: state[n] for n in T}, "segments": [{**s, "start": round(s["start"], 2), "end": round(s["end"], 2)} for s in segs],
            "total_minutes": round(total, 2), "ideal_minutes": round(end, 2), "critical_path": list(reversed(path)), "events": events,
            "all_ok": all(v == "success" for v in state.values()),
            "lesson": "A run is limited by its longest chain of dependent tasks (the critical path) and by how many tasks can run at once. Retries add time; a failed task with no retries left stops everything after it, and a good scheduler marks those as skipped rather than running them on bad input."}


DAG_SAMPLE = {"tasks": "extract_a | - | 10\nextract_b | - | 15 | 1 | 2 | 2\nclean | extract_a, extract_b | 8\nload | clean | 5\nreport | load | 3\nnotify | report | 1", "workers": 2}


# ------------------------------------------------------------ cron
_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
_NAMES = [{}, {}, {}, {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}, {d: i for i, d in enumerate("sun mon tue wed thu fri sat".split())}]


def _field(txt: str, i: int) -> set[int]:
    lo, hi = _RANGES[i]
    out = set()
    for part in txt.lower().split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            if not s.isdigit() or int(s) < 1:
                raise DataLabError(f"Bad step '/{s}' in the cron expression.")
            step = int(s)
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            x, y = part.split("-", 1)
            a, b = _v(x, i), _v(y, i)
        else:
            a = _v(part, i)
            b = hi if step > 1 else a
        if i == 4:
            a, b = (0 if a == 7 and b == 7 else a), b
        if a > b or a < lo or b > (7 if i == 4 else hi):
            raise DataLabError(f"'{txt}' is outside the allowed range {lo} to {hi}.")
        out.update(x % 7 if i == 4 else x for x in range(a, b + 1, step))
    return out


def _v(x: str, i: int) -> int:
    x = x.strip()
    if x in _NAMES[i]:
        return _NAMES[i][x]
    if not x.isdigit():
        raise DataLabError(f"'{x}' is not a number or a name that fits this field.")
    return int(x)


def cron(expr: str, start: str = "", count: int = 5) -> dict:
    p = (expr or "").split()
    if len(p) != 5:
        raise DataLabError("A cron expression has 5 fields: minute hour day-of-month month day-of-week, for example  30 2 * * 1-5")
    if not 1 <= count <= 20:
        raise DataLabError("Ask for 1 to 20 run times.")
    try:
        t = datetime.fromisoformat(start) if start else datetime(2026, 1, 1, 0, 0)
    except ValueError:
        raise DataLabError("Start must look like 2026-03-01 08:30.") from None
    f = [_field(x, i) for i, x in enumerate(p)]
    dom_star, dow_star = p[2].startswith("*"), p[4].startswith("*")
    t = t.replace(second=0, microsecond=0) + timedelta(minutes=1)
    runs = []
    end = t + timedelta(days=366 * 5)
    while t < end and len(runs) < count:
        if t.month not in f[3]:
            t = (t.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
            continue
        dow = (t.weekday() + 1) % 7
        dm, dw = t.day in f[2], dow in f[4]
        day_ok = (dm and dw) if (dom_star or dow_star) else (dm or dw)
        if not day_ok:
            t = t.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        if t.hour not in f[1]:
            t = t.replace(minute=0) + timedelta(hours=1)
            continue
        if t.minute not in f[0]:
            t += timedelta(minutes=1)
            continue
        runs.append(t.strftime("%a %Y-%m-%d %H:%M"))
        t += timedelta(minutes=1)
    plain = f"minute {p[0]}, hour {p[1]}, day of month {p[2]}, month {p[3]}, day of week {p[4]}"
    notes = []
    if not dom_star and not dow_star:
        notes.append("Both day-of-month and day-of-week are set. In standard cron that means EITHER can match, not both. This surprises many people.")
    if p[0] == "*":
        notes.append("The minute is *, so it runs every minute of the matching hours.")
    return {"expression": expr.strip(), "fields": plain, "next_runs": runs, "notes": notes, "timezone": "No time zone: cron uses the server's clock. Daylight-saving changes can skip or repeat a run.",
            "lesson": "Cron is five lists of allowed values. A time matches when every field allows it."}


# ------------------------------------------------------------ stream
def stream(events: str, partitions: int = 3, consumers: int = 2, window: int = 10, kind: str = "tumbling", lateness: int = 2, slide: int = 5, gap: int = 4) -> dict:
    if not 1 <= partitions <= 12 or not 1 <= consumers <= 12:
        raise DataLabError("Partitions and consumers must be 1 to 12.")
    if kind not in ("tumbling", "sliding", "session") or not 1 <= window <= 3600 or not 0 <= lateness <= 3600 or not 1 <= slide <= window or not 1 <= gap <= 3600:
        raise DataLabError("Check the window settings: kind is tumbling, sliding or session; sliding step cannot exceed the window size.")
    ev = []
    for i, l in enumerate(_lines(events, "event line", 1, 500)):
        p = l.split()
        if len(p) != 3:
            raise DataLabError(f"Event '{l}': use 'event_time key value'.")
        try:
            ev.append({"n": i, "t": float(p[0]), "key": p[1], "v": float(p[2])})
        except ValueError:
            raise DataLabError(f"Event '{l}': the time and value must be numbers.") from None
    parts = {i: [] for i in range(partitions)}
    for e in ev:
        pi = zlib.crc32(e["key"].encode()) % partitions
        e["p"] = pi
        e["offset"] = len(parts[pi])
        parts[pi].append(e["n"])
    active = min(consumers, partitions)
    assign = {c: [] for c in range(consumers)}
    for pi in range(partitions):
        assign[pi % consumers].append(pi)
    # watermark processing in arrival order
    wm = float("-inf")
    accepted, late = [], []
    for e in ev:
        if e["t"] < wm:
            late.append(e)
        else:
            accepted.append(e)
        wm = max(wm, e["t"] - lateness)
    wins = {}
    if kind == "session":
        by = {}
        for e in accepted:
            by.setdefault(e["key"], []).append(e)
        for k, es in by.items():
            es.sort(key=lambda x: x["t"])
            cur = [es[0]]
            for x in es[1:]:
                if x["t"] - cur[-1]["t"] <= gap:
                    cur.append(x)
                else:
                    wins[(k, cur[0]["t"], cur[-1]["t"] + gap)] = cur
                    cur = [x]
            wins[(k, cur[0]["t"], cur[-1]["t"] + gap)] = cur
    else:
        step = window if kind == "tumbling" else slide
        for e in accepted:
            s = (e["t"] // step) * step
            while s > e["t"] - window:
                wins.setdefault((e["key"], s, s + window), []).append(e)
                s -= step
    wrows = [{"key": k, "start": a, "end": b, "count": len(es), "sum": sum(x["v"] for x in es)} for (k, a, b), es in sorted(wins.items(), key=lambda z: (z[0][1], z[0][0]))]
    return {"partitions": [{"partition": i, "events": len(parts[i]), "keys": sorted({e["key"] for e in ev if e["p"] == i}), "order": "kept (same key always goes to the same partition)"} for i in parts],
            "assignment": [{"consumer": c, "partitions": a, "idle": not a} for c, a in assign.items()], "idle_consumers": max(0, consumers - active),
            "windows": wrows, "late_dropped": [{"time": e["t"], "key": e["key"], "arrival_number": e["n"] + 1} for e in late], "accepted": len(accepted),
            "lesson": "The key chooses the partition, so events for one key stay in order. A consumer group splits the partitions between its members, so more consumers than partitions leaves some idle. Windows group events by event time; the watermark says how late is too late, and later events are dropped or sent to a side output.",
            "limits": "Simulated in memory with a simple watermark (largest event time seen minus the allowed lateness). Real systems add checkpoints, exactly-once handling and rebalancing."}


STREAM_SAMPLE = {"events": "1 alice 5\n3 bob 2\n4 alice 7\n12 bob 1\n9 alice 3\n2 carol 9\n15 alice 4\n6 bob 8\n21 carol 2", "partitions": 3, "consumers": 4, "window": 10, "kind": "tumbling", "lateness": 2}
SLIPS = ["Streaming overviews say Kafka guarantees ordering. It guarantees order within one partition only, so keys must be chosen to keep related events together.", "Posts describe exactly-once delivery as a switch. It is a property of the whole pipeline (producer, broker, consumer and sink), not of one setting.", "Cron guides say 'day-of-month and day-of-week must both match'. When both are restricted, standard cron runs when either matches."]
NOT_BUILT = ["A real broker or cluster (Kafka, Flink, Spark): the Apache lab teaches those; this simulator shows the ideas.", "Running real jobs: the task graph is a time simulation; the Pipelines page runs real tasks."]
