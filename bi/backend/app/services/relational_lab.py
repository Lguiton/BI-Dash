"""Relational design lab: ERD to tables, keys and dependencies found in real data, relational-model terms, and a reference on
database architecture, scaling, user roles and database products.

Honest limits
* A dependency found in data is evidence, not proof. A functional dependency is a rule about what the data MEANS; a small table can
  satisfy one by coincidence, and a big table can hide one that is broken by a few bad rows. Check with the people who know the business.
* The ERD tool writes DuckDB DDL and tests it on a throw-away in-memory database. It never changes your data.
* Product facts (free-tier limits, popularity shares) come from a course and are dated. Check the vendor's current terms.
* Db2, MySQL, PostgreSQL clusters, replication and sharding cannot run here. This app uses DuckDB.
"""
from __future__ import annotations

import itertools
import re

import duckdb

from app.services import datasets
from app.services.datasets import DataError, q
from app.services.db import get_cursor

TYPES = {"text": "VARCHAR", "integer": "BIGINT", "decimal": "DECIMAL(18,2)", "date": "DATE", "timestamp": "TIMESTAMP", "boolean": "BOOLEAN"}
KINDS = ("1:1", "1:N", "M:N")
_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_ENT, MAX_ATTR, MAX_REL = 12, 14, 20
MAX_COLS, MAX_ROWS = 12, 2_000_000


class RelError(Exception):
    pass


def _ident(v, what) -> str:
    s = str(v or "").strip().lower().replace(" ", "_")
    if not _ID.match(s):
        raise RelError(f"{what} '{v}' should be lower case letters, digits and underscores, starting with a letter.")
    return s


# ---------------------------------------------------------------- 1. ERD -> tables
def erd_to_tables(entities, relationships, audit_columns=False) -> dict:
    if not isinstance(entities, list) or not 1 <= len(entities) <= MAX_ENT:
        raise RelError(f"Give between 1 and {MAX_ENT} entities.")
    rels = relationships or []
    if not isinstance(rels, list) or len(rels) > MAX_REL:
        raise RelError(f"At most {MAX_REL} relationships.")
    ents, notes = {}, []
    for e in entities:
        if not isinstance(e, dict):
            raise RelError("Each entity needs a name and attributes.")
        name = _ident(e.get("name"), "Entity name")
        if name in ents:
            raise RelError(f"Entity '{name}' is listed twice.")
        attrs = e.get("attributes") or []
        if not isinstance(attrs, list) or len(attrs) > MAX_ATTR:
            raise RelError(f"'{name}': at most {MAX_ATTR} attributes.")
        cols, seen = [], set()
        for a in attrs:
            an = _ident(a.get("name") if isinstance(a, dict) else a, f"'{name}' attribute")
            if an in seen:
                raise RelError(f"'{name}' has two attributes called '{an}'.")
            seen.add(an)
            ty = (a.get("type") if isinstance(a, dict) else None) or "text"
            if ty not in TYPES:
                raise RelError(f"'{name}.{an}': type must be one of {', '.join(TYPES)}.")
            cols.append({"name": an, "type": ty, "pk": bool(isinstance(a, dict) and a.get("pk")), "required": bool(isinstance(a, dict) and a.get("required")),
                         "unique": bool(isinstance(a, dict) and a.get("unique")), "default": (a.get("default") if isinstance(a, dict) else None)})
        pks = [c for c in cols if c["pk"]]
        if len(pks) > 1:
            raise RelError(f"'{name}': mark one primary key attribute. (Composite keys appear automatically for many-to-many links.)")
        if not pks:
            pk = f"{name}_id"
            if pk in seen:
                for c in cols:
                    if c["name"] == pk:
                        c["pk"] = True
            else:
                cols.insert(0, {"name": pk, "type": "integer", "pk": True, "required": True, "unique": False, "default": None})
                notes.append(f"{name}: no primary key marked, so '{pk}' was added. Every table needs one unique identifier.")
        ents[name] = {"cols": cols, "fks": [], "extra_unique": set()}
    junctions = {}
    diagram = []
    for r in rels:
        if not isinstance(r, dict):
            raise RelError("Each relationship needs two entities and a kind.")
        a, b = _ident(r.get("a"), "Relationship entity"), _ident(r.get("b"), "Relationship entity")
        kind = r.get("kind")
        if a not in ents or b not in ents:
            raise RelError(f"Relationship {a} - {b}: both must be entities you listed.")
        if a == b:
            raise RelError(f"{a} - {b}: a relationship from an entity to itself (like employee and manager) isn't supported here; add a column by hand.")
        if kind not in KINDS:
            raise RelError("Relationship kind must be 1:1, 1:N or M:N.")
        pk_a = next(c for c in ents[a]["cols"] if c["pk"]); pk_b = next(c for c in ents[b]["cols"] if c["pk"])
        if kind == "1:N":      # one a, many b: foreign key lives on the many side
            fk = f"{a}_{pk_a['name']}" if not pk_a["name"].startswith(a) else pk_a["name"]
            ents[b]["fks"].append((fk, a, pk_a["name"], pk_a["type"], True))
            diagram.append(f"{a} ||--o{{ {b}")
        elif kind == "1:1":
            fk = f"{a}_{pk_a['name']}" if not pk_a["name"].startswith(a) else pk_a["name"]
            ents[b]["fks"].append((fk, a, pk_a["name"], pk_a["type"], True)); ents[b]["extra_unique"].add(fk)
            diagram.append(f"{a} ||--o| {b}")
        else:
            j = f"{a}_{b}"
            if j in ents or j in junctions:
                raise RelError(f"The link table name '{j}' is already used.")
            ca = f"{a}_{pk_a['name']}" if not pk_a["name"].startswith(a) else pk_a["name"]
            cb = f"{b}_{pk_b['name']}" if not pk_b["name"].startswith(b) else pk_b["name"]
            junctions[j] = [(ca, a, pk_a["name"], pk_a["type"]), (cb, b, pk_b["name"], pk_b["type"])]
            diagram.append(f"{a} }}o--o{{ {b}   (via {j})")
            notes.append(f"{a} and {b}: many-to-many can't be stored in two tables, so a link table '{j}' holds one row per pair, with a primary key on both columns together.")
    # order parents first
    deps = {n: {fk[1] for fk in e["fks"]} for n, e in ents.items()}
    order, left = [], dict(deps)
    while left:
        ready = sorted(n for n, d in left.items() if not (d - set(order)))
        if not ready:
            raise RelError("These one-to-many links form a loop (each table needs another to exist first). Break the loop: change one link, or add the foreign key after both tables exist.")
        order += ready
        for n in ready:
            left.pop(n)
    ddl = []
    for n in order:
        e = ents[n]
        lines = []
        for c in e["cols"]:
            s = f"  {c['name']} {TYPES[c['type']]}"
            if c["pk"]:
                s += " PRIMARY KEY"
            else:
                if c["required"]:
                    s += " NOT NULL"
                if c["unique"]:
                    s += " UNIQUE"
                if c["default"] not in (None, ""):
                    d = str(c["default"]).replace("'", "''")[:60]
                    s += f" DEFAULT '{d}'" if c["type"] in ("text", "date", "timestamp") else f" DEFAULT {d}"
            lines.append(s)
        for fk, parent, ppk, pty, req in e["fks"]:
            lines.append(f"  {fk} {TYPES[pty]} NOT NULL{' UNIQUE' if fk in e['extra_unique'] else ''} REFERENCES {parent}({ppk})")
        if audit_columns:
            lines.append("  last_modified TIMESTAMP DEFAULT now()")
        ddl.append(f"CREATE TABLE {n} (\n" + ",\n".join(lines) + "\n);")
    for j, ((ca, a, pa, ta), (cb, b, pb, tb)) in junctions.items():
        ddl.append(f"CREATE TABLE {j} (\n  {ca} {TYPES[ta]} NOT NULL REFERENCES {a}({pa}),\n  {cb} {TYPES[tb]} NOT NULL REFERENCES {b}({pb}),\n  PRIMARY KEY ({ca}, {cb})\n);")
    # prove it runs
    con = duckdb.connect(":memory:")
    try:
        for s in ddl:
            con.execute(s)
        tables = [r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1").fetchall()]
    except Exception as ex:
        raise RelError(f"The generated SQL didn't run: {str(ex)[:300]}") from None
    finally:
        con.close()
    for n, e in ents.items():
        if not any(not c["pk"] for c in e["cols"]) and not e["fks"]:
            notes.append(f"{n} has only a key and no other attributes. Add the properties you want to store about it.")
    notes.append("Tested on a throw-away in-memory database: every statement ran. Add validation (types, ranges), sensible defaults, views for reporting and a 'last modified' column for concurrency checks as your design settles.")
    return {"ddl": ddl, "tables": tables, "diagram": diagram, "notes": notes, "valid": True,
            "lesson": "Entities become tables, attributes become columns, a one-to-many link becomes a foreign key on the many side, and a many-to-many link becomes its own table."}


# ---------------------------------------------------------------- 2. keys and dependencies in data
DEMO_SQL = """CREATE TABLE employee_projects AS SELECT * FROM (VALUES
 (1,101,'Alice','Project X','HR'),(1,102,'Alice','Project Y','Finance'),(2,101,'Bob','Project X','HR'),
 (3,101,'Charlie','Project X','IT'),(3,102,'Charlie','Project Y','Finance')) t(employee_id, project_id, employee_name, project_name, department)"""


def _analyze(cur, table: str, cols: list[dict]) -> dict:
    names = [c["name"] for c in cols]
    n = cur.execute(f"SELECT COUNT(*) FROM {q(table)}").fetchone()[0]
    if n == 0:
        raise RelError("That table has no rows to learn from.")
    if n > MAX_ROWS:
        raise RelError(f"That table has {n:,} rows. Analyze a sample of up to {MAX_ROWS:,} rows.")
    if len(names) > MAX_COLS:
        raise RelError(f"That table has {len(names)} columns. This tool compares up to {MAX_COLS}: make a narrower table first.")
    nulls = {c: cur.execute(f"SELECT COUNT(*) - COUNT({q(c)}) FROM {q(table)}").fetchone()[0] for c in names}
    # candidate keys: minimal column sets with no NULLs whose values are unique
    keys: list[tuple[str, ...]] = []
    for size in (1, 2, 3):
        for combo in itertools.combinations([c for c in names if nulls[c] == 0], size):
            if any(set(k) <= set(combo) for k in keys):
                continue
            d = cur.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {', '.join(q(c) for c in combo)} FROM {q(table)})").fetchone()[0]
            if d == n:
                keys.append(combo)
        if len(keys) >= 6:
            break
    keyset = {c for k in keys for c in k}
    # single-column functional dependencies A -> B that hold with no exceptions
    fds = []
    for a in names:
        others = [b for b in names if b != a]
        if not others:
            continue
        sel = ", ".join(f"COUNT(DISTINCT {q(b)}) AS d{i}" for i, b in enumerate(others))
        row = cur.execute(f"SELECT {', '.join(f'COUNT(*) FILTER (WHERE d{i} > 1)' for i in range(len(others)))} FROM (SELECT {sel} FROM {q(table)} GROUP BY {q(a)})").fetchone()
        distinct_a = cur.execute(f"SELECT COUNT(DISTINCT {q(a)}) FROM {q(table)}").fetchone()[0]
        for b, bad in zip(others, row):
            if bad == 0 and distinct_a < n:   # a repeats, so the rule really was tested
                db = cur.execute(f"SELECT COUNT(DISTINCT {q(b)}) FROM {q(table)}").fetchone()[0]
                if db > 1:
                    fds.append({"lhs": a, "rhs": b})
    hints = []
    composite = [k for k in keys if len(k) > 1]
    single = {k[0] for k in keys if len(k) == 1}
    for f in fds:
        a, b = f["lhs"], f["rhs"]
        part = next((k for k in composite if a in k and b not in k), None)
        if part and a not in single:
            hints.append({"kind": "partial", "text": f"{b} depends on {a} alone, which is only part of the key ({' + '.join(part)}). That is a partial dependency: '{b}' is repeated on every row for the same {a}, and a change must be made in many places (breaks 2nd normal form). Move {a} and {b} to their own table."})
        elif b not in keyset and a not in keyset:
            hints.append({"kind": "transitive", "text": f"{b} depends on {a}, and {a} is not a key. That is a transitive dependency (breaks 3rd normal form): '{b}' repeats for each {a}. Move {a} and {b} to their own table and keep {a} here as a reference."})
    if not keys:
        hints.append({"kind": "nokey", "text": "No unique column combination of up to 3 columns (without blanks) exists, so rows can repeat. Add an identifier or fix duplicates before designing around this table."})
    return {"table": table, "degree": len(names), "cardinality": n, "schema": [{"name": c["name"], "type": c["type"]} for c in cols],
            "candidate_keys": [list(k) for k in keys], "dependencies": fds, "hints": hints,
            "caution": "These hold in THIS data. A rule seen in a small table may be coincidence, and a business rule broken by a few bad rows will not show up. Confirm each one with someone who knows what the columns mean.",
            "lesson": "Degree is the number of columns, cardinality the number of rows. A candidate key is a minimal set of columns that uniquely identifies every row; A -> B means each value of A goes with exactly one value of B."}


def analyze(table: str | None = None, demo: bool = False) -> dict:
    if demo or not table:
        con = duckdb.connect(":memory:")
        try:
            con.execute(DEMO_SQL)
            cols = [{"name": r[0], "type": r[1]} for r in con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='employee_projects' ORDER BY ordinal_position").fetchall()]
            out = _analyze(con, "employee_projects", cols)
        finally:
            con.close()
        out["demo"] = True
        return out
    try:
        cols = datasets.table_columns(table)
    except DataError as e:
        raise RelError(str(e)) from e
    with get_cursor() as cur:
        out = _analyze(cur, table, cols)
    out["demo"] = False
    return out


def _check_cols(cols, valid, what):
    if not isinstance(cols, list) or not cols or len(cols) > 4 or any(c not in valid for c in cols):
        raise RelError(f"{what}: pick 1 to 4 columns from the table.")
    return list(dict.fromkeys(cols))


def check_dependency(table: str | None, kind: str, lhs: list, rhs: list, demo: bool = False) -> dict:
    """Test a rule X -> Y (functional) or X ->> Y (multi-valued) against the data and show where it breaks."""
    if kind not in ("fd", "mvd"):
        raise RelError("kind must be fd or mvd.")
    con = None
    try:
        if demo or not table:
            con = duckdb.connect(":memory:"); con.execute(DEMO_SQL); cur, t = con, "employee_projects"
            valid = [r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employee_projects' ORDER BY ordinal_position").fetchall()]
            ctx = None
        else:
            try:
                valid = [c["name"] for c in datasets.table_columns(table)]
            except DataError as e:
                raise RelError(str(e)) from e
            ctx = get_cursor(); cur = ctx.__enter__(); t = table
        try:
            lhs, rhs = _check_cols(lhs, valid, "Left side"), _check_cols(rhs, valid, "Right side")
            if set(lhs) & set(rhs):
                raise RelError("The two sides share a column; pick different ones.")
            ql, qr = ", ".join(q(c) for c in lhs), ", ".join(q(c) for c in rhs)
            if kind == "fd":
                rows = cur.execute(f"SELECT {ql}, COUNT(DISTINCT ({qr})) AS different_values FROM {q(t)} GROUP BY {ql} HAVING COUNT(DISTINCT ({qr})) > 1 ORDER BY 2 DESC LIMIT 8").fetchall()
                total = cur.execute(f"SELECT COUNT(*) FROM (SELECT {ql} FROM {q(t)} GROUP BY {ql} HAVING COUNT(DISTINCT ({qr})) > 1)").fetchone()[0]
                text = (f"{' + '.join(lhs)} -> {' + '.join(rhs)} holds: every value of {' + '.join(lhs)} goes with exactly one {' + '.join(rhs)}." if total == 0
                        else f"{' + '.join(lhs)} -> {' + '.join(rhs)} does NOT hold: {total:,} value(s) of {' + '.join(lhs)} go with more than one {' + '.join(rhs)}.")
                return {"holds": total == 0, "text": text, "violations": [{"left": [str(x) for x in r[:-1]], "different_values": r[-1]} for r in rows], "violation_groups": total}
            rest = [c for c in valid if c not in lhs and c not in rhs]
            if not rest:
                return {"holds": True, "text": "With no other columns left, a multi-valued dependency is trivially true. Add a third column to give it meaning.", "violations": [], "violation_groups": 0}
            qz = ", ".join(q(c) for c in rest)
            # X ->> Y holds when, for each X, the (Y, Z) rows are exactly every Y paired with every Z
            sql = (f"SELECT {ql}, COUNT(DISTINCT ({qr})) AS ys, COUNT(DISTINCT ({qz})) AS zs, COUNT(DISTINCT ({qr}, {qz})) AS pairs FROM {q(t)} GROUP BY {ql}")
            rows = cur.execute(sql).fetchall()
            bad = [r for r in rows if r[-1] != r[-3] * r[-2]]
            text = (f"{' + '.join(lhs)} ->> {' + '.join(rhs)} holds: for each {' + '.join(lhs)}, the {' + '.join(rhs)} values combine with every combination of {', '.join(rest)} (they vary independently)." if not bad
                    else f"{' + '.join(lhs)} ->> {' + '.join(rhs)} does NOT hold: for {len(bad)} value(s) of {' + '.join(lhs)}, not every {' + '.join(rhs)} appears with every {', '.join(rest)}. That is expected when the other columns depend on {' + '.join(rhs)}.")
            return {"holds": not bad, "text": text, "other_columns": rest, "violation_groups": len(bad),
                    "violations": [{"left": [str(x) for x in r[:-3]], "ys": r[-3], "zs": r[-2], "rows_found": r[-1], "rows_if_independent": r[-3] * r[-2]} for r in bad[:8]]}
        finally:
            if ctx is not None:
                ctx.__exit__(None, None, None)
    finally:
        if con is not None:
            con.close()


# ---------------------------------------------------------------- 3. reference
CONCEPTS = [
    ("Set", "A collection of unique elements with no order. Operations: membership, subset, union, intersection, difference, empty set, power set, universal set, disjoint sets."),
    ("Relation", "A set of tuples: connections between elements of sets. A binary relation links two elements, such as 3 < 5."),
    ("Properties of a relation", "Reflexive (every element relates to itself, like equals), symmetric (A to B means B to A, like 'is a sibling of'), transitive (A to B and B to C means A to C, like less than) and anti-symmetric (A to B and B to A means A = B, like less than or equal)."),
    ("Relation schema", "The structure: the relation's name, and the name and type of each column (attribute). Author(author_id CHAR, last_name VARCHAR, ...)."),
    ("Relation instance", "The actual data at a moment: rows (tuples) under those columns. The schema rarely changes; the instance changes all the time."),
    ("Degree", "The number of attributes (columns)."), ("Cardinality", "The number of tuples (rows). Careful: in ER diagrams 'cardinality' also means how many of one entity link to another (1:1, 1:N, M:N)."),
    ("Primary key", "The one candidate key you choose to identify rows. Never blank, never repeated."), ("Foreign key", "A column holding another table's primary key. It is how tables link and how the database refuses an order for a customer that doesn't exist."),
]
TOPOLOGIES = [
    ("Single-tier", "Interface, logic and data on one machine.", "A desktop app with its own database file, or this app on your laptop.", "Simple, but one failure or one overloaded machine takes everything with it."),
    ("Two-tier (client-server)", "Clients talk straight to a remote database server through a driver or API (ODBC, JDBC).", "A reporting tool pointed at a database.", "Every client needs database access, which makes security and load harder to control."),
    ("Three-tier", "Clients talk to an application server, which alone talks to the database.", "A banking app: phone, app server, database servers.", "The usual production design: the database is reachable only by the application tier and administrators, for security, performance and maintainability."),
    ("Cloud", "The database runs as a managed service. No software to install or maintain; reachable from anywhere with an internet connection.", "Amazon RDS, Db2 on Cloud, Azure SQL, Oracle Cloud.", "Handy for development, test and production. You trade control for convenience, and need to watch cost, data location and exit."),
]
DISTRIBUTED = [
    ("Shared disk", "Several database servers work in parallel on the same shared storage, linked by a fast interconnect. If a server fails, clients are rerouted to another.", "Scales processing; the shared storage is the one thing to protect."),
    ("Shared nothing", "Each node has its own CPU, memory and storage. Data is spread by replication or partitioning, and clients are rerouted if a node fails.", "Scales out by adding nodes; the common design for warehouses."),
    ("Replication", "Copy changes from one server to replicas. Same-site replicas give high availability (HA); replicas in other places give disaster recovery (DR) and spread read load.", "A replica is not a backup: a bad delete is copied too."),
    ("Partitioning and sharding", "Split a big table into logical pieces (for example sales by quarter). Sharding puts those pieces on separate nodes, each with its own compute, so a query runs in parallel and results are combined.", "Common for warehouses and BI. Choose the split key carefully: a bad key makes one shard do all the work."),
    ("Clustering", "Several independent machines working together as one system.", "Needs a plan for failover and for what happens when nodes disagree."),
]
ROLES = [
    ("Data engineers and DBAs", "Create and look after database objects, set access controls, monitor and tune performance.", "Graphical or web admin tools, command line (for example mysqldump, db2 clp, sqlplus), SQL scripts, administration APIs."),
    ("Data scientists and business analysts", "Read data to analyze it and predict; sometimes build objects in a sandbox.", "Jupyter, RStudio, Zeppelin, SAS, SPSS; Excel, Power BI, Tableau, MicroStrategy; SQL query tools."),
    ("Application developers", "Rarely query by hand: their programs read and write data.", "Languages (Python, Java, C#, JavaScript, PHP, Ruby) through ODBC/JDBC or REST, usually via an ORM such as Django, Hibernate, Entity Framework, ActiveRecord or Sequelize."),
]
HISTORY = [
    ("1960s", "IBM and American Airlines build the Sabre reservation system. The course calls it the first product recognizable as a relational database; Sabre was an early large reservation system, and the relational model itself came in 1970, so treat that wording loosely."),
    ("1970-1976", "Edgar Codd sets out the relational model and rules for it; Peter Chen introduces the entity-relationship model (1976)."),
    ("Late 1970s", "Ingres (Berkeley) and System R (IBM) are running."), ("1980s", "Commercial success; SQL becomes the standard query language; Db2 is IBM's flagship (first released 1983)."),
    ("1990s", "Client-server systems and desktop tools such as ODBC, Excel and Access spread. Oracle, SQL Server and Db2 lead."), ("Late 2000s", "Open source rises: MySQL, PostgreSQL, SQLite."),
    ("2010s", "Cloud databases take off: Amazon RDS, Db2 on Cloud, Azure SQL, Oracle Cloud."),
]
PRODUCTS = [
    {"name": "Db2 (IBM)", "facts": ["First released 1983 on mainframes; now a family: Db2 database (OLTP), Db2 Warehouse (analytics, parallel processing, column store, data skipping), Db2 on Cloud, Db2 Warehouse on Cloud, Db2 Big SQL (SQL on Hadoop), Db2 for z/OS.", "One common SQL engine across the family, so a query written once works across products.", "HADR (high availability disaster recovery) replicates a primary to several standby servers and can promote one automatically.", "Db2 Warehouse scales by adding data nodes; partitions rebalance."], "free": "The course lists a free community licence (100 GB limit), a free Docker image and a free Lite cloud plan (200 MB, 15 connections). Limits change: check IBM's current terms."},
    {"name": "MySQL (Oracle)", "facts": ["Relational, open source under GPL with a commercial licence for embedding; MariaDB is a well-known fork. (The course calls it object-relational; it is usually described as relational.)", "Storage engines decide what a table can do: InnoDB (default; transactions, row-level locking, clustered primary-key index, foreign keys), MyISAM (read-heavy, table-level locking, no transactions) and NDB (for MySQL Cluster).", "Replication copies a source to replicas to spread reads and allow failover. Clustering options: InnoDB with group replication (one read-write primary plus secondaries, MySQL Router balances), and MySQL Cluster with NDB (in-memory data nodes)."], "free": "Community edition is free and open source."},
    {"name": "PostgreSQL", "facts": ["Open source (permissive PostgreSQL licence), object-relational: supports inheritance and overloading; extensions such as PostGIS for spatial data; JSON and HSTORE for semi-structured data.", "Replication: two-node synchronous, multi-node asynchronous with read-only replicas; commercial add-ons offer multi-master.", "Newer releases add table partitioning and ways to spread partitions across servers (sharding)."], "free": "Free and open source."},
    {"name": "SQLite", "facts": ["A small database in a single file, public domain, no server. Very widely embedded (apps, browsers, phones). This app keeps its own settings in SQLite."], "free": "Free."},
]
LICENSING = "Course figures, dated: in 2021 the ten most popular systems in DB-Engines' ranking included Oracle, MySQL, SQL Server, PostgreSQL, MongoDB, Redis, Elasticsearch, Db2, SQLite and Access; a 2023 study put open-source systems at about 55% of the popularity score, up from about 35% in 2013, and experts predicted 80% of databases would be on or moving to the cloud by 2025. Popularity scores count mentions, searches and job posts, not quality or fit, and the figures are old: check db-engines.com for today's."
PRACTICES = [("Pick a primary key", "A unique identifier for every row (book_id)."), ("Validate data", "Types, ranges and formats (a year must be a number in a sensible range)."),
             ("Set sensible defaults", "Such as 'Unknown' for a missing author, so entry is quicker and gaps are visible."), ("Use views", "A saved query that shows a simple, combined picture (books with authors) without the join."),
             ("Plan for concurrency", "Several people change data at once. Locking, transactions and a 'last modified' timestamp help detect clashes.")]
SLIPS = [
    "The course reading says reflexivity is 'X -> X'. The rule is: if Y is part of X then X -> Y (a set of columns determines each of its own columns).",
    "It says closure is 'the minimal set of FDs that implies all others'. That is a minimal (canonical) cover. The closure of a column set X is every column X determines, and the closure of a set of FDs is every FD it implies.",
    "Its worked example calls EmployeeID alone a candidate key, but the sample table repeats EmployeeID (Alice appears twice). The real candidate key there is EmployeeID + ProjectID. The Keys and dependencies tab runs that exact table so you can see it.",
    "Its mapping example puts 'author' as a column of the book table. That works for one author per book; with several authors per book use a link table (the ERD tool builds it).",
    "'Cardinality' means row count in the relational model but 1:1 / 1:N / M:N in ER diagrams. Say which you mean.",
]


def reference() -> dict:
    return {"concepts": [{"term": a, "what": b} for a, b in CONCEPTS], "topologies": [{"name": a, "what": b, "example": c, "note": d} for a, b, c, d in TOPOLOGIES],
            "distributed": [{"name": a, "what": b, "note": c} for a, b, c in DISTRIBUTED], "roles": [{"role": a, "does": b, "tools": c} for a, b, c in ROLES],
            "history": [{"when": a, "what": b} for a, b in HISTORY], "products": PRODUCTS, "licensing": LICENSING, "practices": [{"name": a, "what": b} for a, b in PRACTICES],
            "slips": SLIPS, "types": list(TYPES), "kinds": list(KINDS),
            "example": {"entities": [{"name": "author", "attributes": [{"name": "author_id", "type": "integer", "pk": True}, {"name": "last_name", "required": True}, {"name": "first_name"}, {"name": "email", "unique": True}, {"name": "city"}, {"name": "country"}]},
                                     {"name": "book", "attributes": [{"name": "book_id", "type": "integer", "pk": True}, {"name": "title", "required": True}, {"name": "edition", "type": "integer"}, {"name": "year", "type": "integer"}, {"name": "price", "type": "decimal"}]}],
                        "relationships": [{"a": "author", "b": "book", "kind": "M:N"}]},
            "note": "Based on a database fundamentals course. Course product details and statistics are dated; the dependency tests run on your own tables or the built-in example."}
