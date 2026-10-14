"""Runtime configuration, read from environment variables (or a .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:3001,http://localhost:3012"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_UPLOAD_ROWS = 200_000
MAX_TABLE_UPLOAD_BYTES = 50 * 1024 * 1024   # "My data" imports of any CSV
MAX_TABLE_ROWS = 1_000_000


def db_path() -> Path:
    """The Practice workspace's database file (the original single-database location, so existing data is kept)."""
    return Path(os.environ.get("BI_DB_PATH", BASE_DIR / "data" / "bi_warehouse.duckdb"))


def workspace_paths() -> dict[str, Path]:
    """Practice and Real are separate DuckDB files, so practice data and your real data can never mix."""
    p = db_path()
    return {"practice": p, "real": p.with_name(f"{p.stem}_real{p.suffix}")}


def state_path() -> Path:
    """Small SQLite file for things that must survive switching workspaces: study progress, settings, sources, audit log."""
    p = db_path()
    return p.with_name(f"{p.stem}_state.sqlite")


def backups_dir() -> Path:
    return Path(os.environ.get("BI_BACKUP_DIR", db_path().parent / "backups"))


def models_dir() -> Path:
    return Path(os.environ.get("BI_MODELS_DIR", db_path().parent / "models"))


def source_dirs() -> list[Path]:
    """Folders the file connector may read. The inbox is always allowed; add more with BI_SOURCE_DIRS (separated by ':' or ';')."""
    inbox = Path(os.environ.get("BI_INBOX_DIR", db_path().parent / "inbox"))
    extra = [Path(x).expanduser() for x in os.environ.get("BI_SOURCE_DIRS", "").replace(";", ":").split(":") if x.strip()]
    return [inbox, *extra]


def scheduler_enabled() -> bool:
    return os.environ.get("BI_SCHEDULER", "1") != "0"


def cors_origins() -> list[str]:
    raw = os.environ.get("BI_CORS_ORIGINS", DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def seed_demo_enabled() -> bool:
    return os.environ.get("BI_SEED_DEMO", "1") != "0"
