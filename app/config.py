"""Plan365 configuration constants."""
import os
from pathlib import Path

SECRET_KEY = os.environ.get(
    "PLAN365_SECRET_KEY",
    "plan365-change-me-in-production-use-openssl-rand-hex-32",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("PLAN365_JWT_HOURS", "24"))
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Database backend: "sqlite" (default, SBC) | "postgresql"
DB_BACKEND = (os.environ.get("PLAN365_DB_BACKEND") or "sqlite").strip().lower()
if DB_BACKEND in ("postgres", "pgsql", "pg"):
    DB_BACKEND = "postgresql"
if DB_BACKEND not in ("sqlite", "postgresql"):
    raise RuntimeError(f"Unsupported PLAN365_DB_BACKEND={DB_BACKEND!r} (use sqlite|postgresql)")

# SQLite file path (ignored when postgresql)
DB_PATH = Path(os.environ.get("PLAN365_DB", str(BASE_DIR / "plan365.db")))

# PostgreSQL connection URL, e.g.
#   postgresql://plan365:plan365@localhost:5432/plan365
DATABASE_URL = os.environ.get("PLAN365_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""

TYPES = ["2D CAD", "CAD", "CAM", "Tools", "Others"]
PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["Todo", "In Progress", "Review", "Testing", "Done", "Blocked", "Handoff"]
PROJECT_STATUSES = ["Active", "On Hold", "Completed", "Archived"]
