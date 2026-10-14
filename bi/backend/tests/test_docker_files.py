"""Docker files are checked statically here (Docker itself is exercised by the 'docker' CI job): the compose file parses, every file
it points at exists, the ports and volumes are safe, and the images never bake in secrets."""
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def test_compose_has_the_two_app_services_and_an_optional_database():
    s = COMPOSE["services"]
    assert {"backend", "frontend", "db"} <= set(s)
    assert s["db"]["profiles"] == ["postgres"]            # off unless asked for
    assert s["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"


def test_every_build_input_exists():
    for name in ("backend", "frontend"):
        b = COMPOSE["services"][name]["build"]
        ctx = ROOT / b["context"]
        assert ctx.is_dir()
        df = ctx / b.get("dockerfile", "Dockerfile")
        assert df.is_file(), df
        for line in df.read_text().splitlines():
            m = re.match(r"COPY\s+(?:--\S+\s+)?(\S+)\s+\S+", line)
            if m and m.group(1) not in (".", "./"):
                for src in m.group(1).split():
                    assert (ctx / src).exists(), f"{df.name}: COPY source {src} missing"


def test_there_is_no_login_so_every_port_stays_on_this_computer():
    for name, svc in COMPOSE["services"].items():
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{name} publishes {p} to the whole network"


def test_the_database_lives_on_a_volume_and_the_health_check_hits_a_real_route():
    be = COMPOSE["services"]["backend"]
    path = be["environment"]["BI_DB_PATH"]
    assert any(v.split(":")[1] == str(Path(path).parent).replace("\\", "/") for v in be["volumes"]), "data would vanish with the container"
    main = (ROOT / "backend/app/main.py").read_text()
    assert '@app.get("/health")' in main and "/health" in " ".join(be["healthcheck"]["test"])


def test_browser_and_api_addresses_agree():
    fe = COMPOSE["services"]["frontend"]["build"]["args"]["NEXT_PUBLIC_API_URL"]
    be = COMPOSE["services"]["backend"]
    assert fe == "http://localhost:8020" and "127.0.0.1:8020:8020" in be["ports"]
    assert be["environment"]["BI_CORS_ORIGINS"] == "http://localhost:3000"
    assert (ROOT / "frontend/Dockerfile").read_text().count("3000") >= 2


def test_secrets_are_never_baked_in():
    text = (ROOT / "docker-compose.yml").read_text() + (ROOT / "backend/Dockerfile").read_text() + (ROOT / "frontend/Dockerfile").read_text()
    assert not re.search(r"(API_KEY|PASSWORD)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{12,}", text.replace("bi_practice", ""))
    ignore = (ROOT / ".dockerignore").read_text()
    assert "**/.env" in ignore and "node_modules" in ignore and "*.duckdb" in ignore
    assert "COPY . ." not in (ROOT / "backend/Dockerfile").read_text()           # the backend image copies named folders only
    for f in ("frontend/.dockerignore",):
        assert ".env" in (ROOT / f).read_text()


def test_the_backend_image_carries_what_the_app_reads_at_run_time():
    df = (ROOT / "backend/Dockerfile").read_text()
    for needed in ("COPY backend backend", "COPY docs docs", "COPY data_samples data_samples"):
        assert needed in df
    assert "USER bi" in df and "10001" in df          # not root
