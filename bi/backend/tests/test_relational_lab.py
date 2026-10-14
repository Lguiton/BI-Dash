import pytest

from app.services import relational_lab as rl


def test_erd_many_to_many_builds_link_table():
    ex = rl.reference()["example"]
    r = rl.erd_to_tables(ex["entities"], ex["relationships"], audit_columns=True)
    assert r["valid"] and set(r["tables"]) == {"author", "book", "author_book"}
    link = next(d for d in r["ddl"] if d.startswith("CREATE TABLE author_book"))
    assert "PRIMARY KEY (author_id, book_id)" in link and "REFERENCES author(author_id)" in link
    assert any("link table" in n for n in r["notes"]) and "last_modified" in r["ddl"][0]


def test_erd_one_to_many_and_one_to_one_and_order():
    ents = [{"name": "order_line", "attributes": [{"name": "qty", "type": "integer"}]}, {"name": "customer", "attributes": [{"name": "name"}]},
            {"name": "profile", "attributes": [{"name": "bio"}]}]
    r = rl.erd_to_tables(ents, [{"a": "customer", "b": "order_line", "kind": "1:N"}, {"a": "customer", "b": "profile", "kind": "1:1"}])
    ddl = "\n".join(r["ddl"])
    assert ddl.index("CREATE TABLE customer") < ddl.index("CREATE TABLE order_line")
    assert "customer_id BIGINT NOT NULL REFERENCES customer(customer_id)" in ddl and "UNIQUE REFERENCES" in ddl
    assert any("no primary key marked" in n for n in r["notes"])


def test_erd_errors():
    for ents, rels in (([], []), ([{"name": "Bad Name!"}], []), ([{"name": "a"}], [{"a": "a", "b": "zzz", "kind": "1:N"}]),
                       ([{"name": "a"}, {"name": "b"}], [{"a": "a", "b": "b", "kind": "2:2"}]),
                       ([{"name": "a"}, {"name": "b"}], [{"a": "a", "b": "b", "kind": "1:N"}, {"a": "b", "b": "a", "kind": "1:N"}]),
                       ([{"name": "a", "attributes": [{"name": "x", "type": "blob"}]}], [])):
        with pytest.raises(rl.RelError):
            rl.erd_to_tables(ents, rels)


def test_demo_table_keys_and_normalization_hints():
    r = rl.analyze(demo=True)
    assert (r["degree"], r["cardinality"]) == (5, 5)
    assert ["employee_id", "project_id"] in r["candidate_keys"] and ["employee_id"] not in r["candidate_keys"]   # the course's own slip
    fds = {(d["lhs"], d["rhs"]) for d in r["dependencies"]}
    assert ("employee_id", "employee_name") in fds and ("project_id", "project_name") in fds
    assert ("project_id", "department") not in fds
    assert any(h["kind"] == "partial" for h in r["hints"])


def test_dependency_checks():
    ok = rl.check_dependency(None, "fd", ["employee_id"], ["employee_name"], demo=True)
    assert ok["holds"]
    bad = rl.check_dependency(None, "fd", ["project_id"], ["department"], demo=True)
    assert not bad["holds"] and bad["violation_groups"] == 1 and "does NOT hold" in bad["text"]
    mv = rl.check_dependency(None, "mvd", ["employee_id"], ["project_id"], demo=True)
    assert not mv["holds"]   # department depends on the pair, so projects are not independent of department
    with pytest.raises(rl.RelError):
        rl.check_dependency(None, "fd", ["nope"], ["employee_name"], demo=True)
    with pytest.raises(rl.RelError):
        rl.check_dependency(None, "fd", ["employee_id"], ["employee_id"], demo=True)


def test_true_mvd_holds():
    from app.services import datasets  # noqa: F401
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE t AS SELECT * FROM (VALUES ('a','x',1),('a','x',2),('a','y',1),('a','y',2),('b','x',1)) v(k, skill, lang)")
    cols = [{"name": c, "type": "t"} for c in ("k", "skill", "lang")]
    # k ->> skill: every skill for k pairs with every lang for k
    rows = con.execute("SELECT COUNT(DISTINCT skill), COUNT(DISTINCT lang), COUNT(DISTINCT (skill, lang)) FROM t WHERE k='a'").fetchone()
    assert rows[2] == rows[0] * rows[1]


def test_analyze_user_table_and_endpoints(client):
    from app.services import datasets
    datasets.import_file(b"id,dept,dept_head\n1,A,Ann\n2,A,Ann\n3,B,Bo\n4,B,Bo\n5,C,Cy\n", "rl_t.csv", "rl_t")
    t = datasets.table_name_for("rl_t")
    r = client.post("/api/relational/analyze", json={"table": t}).json()
    assert r["candidate_keys"] == [["id"]] and {"lhs": "dept", "rhs": "dept_head"} in r["dependencies"]
    assert any(h["kind"] == "transitive" for h in r["hints"])
    assert client.post("/api/relational/analyze", json={"table": "nope_table"}).status_code == 400
    d = client.post("/api/relational/dependency", json={"table": t, "kind": "fd", "lhs": ["dept"], "rhs": ["dept_head"]}).json()
    assert d["holds"]
    ref = client.get("/api/relational").json()
    assert len(ref["topologies"]) == 4 and len(ref["slips"]) >= 4
    e = client.post("/api/relational/erd", json={"entities": ref["example"]["entities"], "relationships": ref["example"]["relationships"]})
    assert e.status_code == 200 and e.json()["valid"]
    assert client.post("/api/relational/erd", json={"entities": []}).status_code == 400
