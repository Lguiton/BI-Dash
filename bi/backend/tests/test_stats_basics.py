import io
import random

import pytest

from app.services import stats_basics

T = "sb_t"


def _data(client):
    random.seed(11)
    rows = ["age,income,region,bought,size,temp_c"]
    for i in range(400):
        inc = max(1, int(random.gauss(60, 20)))
        reg = random.choice(["N", "N", "N", "S", "S", "E"])
        buy = "yes" if random.random() < (0.6 if reg == "N" else 0.2) else "no"
        rows.append(f"{random.randint(18, 70)},{inc},{reg},{buy},{random.choice(['low', 'medium', 'high'])},{random.randint(-5, 30)}")
    r = client.post("/api/data/import", data={"table": T, "mode": "replace"}, files={"file": ("t.csv", io.BytesIO("\n".join(rows).encode()), "text/csv")})
    assert r.status_code == 200, r.text


def test_variable_types(client):
    _data(client)
    d = client.get("/api/stats/variables", params={"source": T}).json()
    by = {c["column"]: c for c in d["columns"]}
    assert by["region"]["type"] == "categorical" and by["region"]["level"] == "nominal"
    assert by["size"]["level"] == "ordinal"
    assert by["income"]["type"] == "numerical" and by["income"]["level"] == "ratio"
    assert by["temp_c"]["level"] == "interval"


def test_frequency_pareto(client):
    _data(client)
    d = client.post("/api/stats/frequency", json={"source": T, "column": "region"}).json()
    assert d["table"][0]["value"] == "N" and d["table"][-1]["cumulative"] == 1.0
    assert [t["absolute"] for t in d["table"]] == sorted([t["absolute"] for t in d["table"]], reverse=True)
    assert abs(sum(t["relative"] for t in d["table"]) - 1) < 0.01


def test_crosstab_chi_square(client):
    _data(client)
    d = client.post("/api/stats/crosstab", json={"source": T, "row_col": "region", "col_col": "bought"}).json()
    assert d["p"] < 0.001 and d["n"] == 400 and 0 < d["cramers_v"] < 1
    assert client.post("/api/stats/crosstab", json={"source": T, "row_col": "region", "col_col": "region"}).status_code == 400
    assert client.post("/api/stats/crosstab", json={"source": T, "row_col": "age", "col_col": "region"}).status_code == 400


def test_mean_test_t_and_z(client):
    _data(client)
    d = client.post("/api/stats/meantest", json={"source": T, "column": "income", "mu0": 60}).json()
    assert d["statistic_name"] == "t" and d["df"] == 399 and 0 <= d["p_value"] <= 1 and d["decision"] in ("reject H0", "fail to reject H0")
    far = client.post("/api/stats/meantest", json={"source": T, "column": "income", "mu0": 40, "alternative": "greater"}).json()
    assert far["reject"] is True and far["power"] > 0.9
    z = client.post("/api/stats/meantest", json={"source": T, "column": "income", "mu0": 60, "sigma": 20}).json()
    assert z["statistic_name"] == "z" and z["df"] is None
    assert client.post("/api/stats/meantest", json={"source": T, "column": "income", "mu0": 60, "alternative": "sideways"}).status_code == 422
    assert client.post("/api/stats/meantest", json={"source": T, "column": "region", "mu0": 1}).status_code == 400


def test_sampling_matches_the_formula(client):
    _data(client)
    d = client.post("/api/stats/sampling", json={"source": T, "column": "income", "n": 40, "reps": 800}).json()
    s = d["sampling"]
    assert abs(s["std_error_observed"] - s["std_error_formula"]) / s["std_error_formula"] < 0.15
    assert client.post("/api/stats/sampling", json={"source": T, "column": "income", "n": 400}).status_code == 400


def test_margin_and_sample_size(client):
    m = client.post("/api/stats/margin", json={"sd": 10, "n": 100}).json()
    assert abs(m["margin_of_error"] - 1.96) < 0.01
    n = client.post("/api/stats/margin", json={"sd": 10, "margin": 1}).json()
    assert n["n_needed"] == 385
    assert client.post("/api/stats/margin", json={"sd": 10, "margin": 1, "n": 10}).status_code == 400
    assert client.post("/api/stats/margin", json={"sd": 10}).status_code == 400


def test_descriptive_extras(client):
    _data(client)
    d = client.post("/api/stats/distribution", json={"source": T, "column": "income"}).json()
    dd = d["dispersion"]
    assert dd["population_sd"] < dd["sd"] and dd["cv"] > 0 and d["histogram"][-1]["cumulative"] == 1.0
    c = client.post("/api/stats/correlation", json={"source": T, "columns": ["age", "income"]}).json()["pairs"][0]
    assert "cov_sample" in c and abs(c["cov_population"]) <= abs(c["cov_sample"])


def test_zscore_column(client):
    _data(client)
    j = client.post("/api/stats/clean", json={"table": T, "new_table": "sb_z", "steps": [{"op": "add_feature", "how": "zscore", "name": "income_z", "a": "income"}]})
    assert j.status_code == 200, j.text
    d = client.post("/api/stats/distribution", json={"source": "sb_z", "column": "income_z"}).json()
    assert abs(d["central"]["mean"]) < 0.01 and abs(d["dispersion"]["sd"] - 1) < 0.01


def test_agent_analyze_stats_kinds(client):
    from app.services import agents
    _data(client)
    for args in ({"kind": "variables", "source": T}, {"kind": "frequency", "source": T, "column": "region"},
                 {"kind": "crosstab", "source": T, "columns": ["region", "bought"]}, {"kind": "test_mean", "source": T, "column": "income", "mu0": 60}):
        assert agents._analyze(args, True)
    with pytest.raises(agents.AgentError):
        agents._analyze({"kind": "test_mean", "source": T, "column": "income"}, True)
    assert "inference" in __import__("app.services.ai_work", fromlist=["TYPES"]).TYPES
