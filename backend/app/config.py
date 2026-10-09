"""Runtime configuration, read from environment variables (or a .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:3001,http://localhost:3012"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_UPLOAD_ROWS = 200_000


def db_path() -> Path:
    return Path(os.environ.get("BI_DB_PATH", BASE_DIR / "data" / "bi_warehouse.duckdb"))


def cors_origins() -> list[str]:
    raw = os.environ.get("BI_CORS_ORIGINS", DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def seed_demo_enabled() -> bool:
    return os.environ.get("BI_SEED_DEMO", "1") != "0"
