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
DB_PATH = Path(os.environ.get("PLAN365_DB", str(BASE_DIR / "plan365.db")))
STATIC_DIR = BASE_DIR / "static"

# PostgreSQL configuration (optional, enabled via USE_POSTGRES=true)
USE_POSTGRES = os.environ.get("USE_POSTGRES", "false").lower() == "true"
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "plan365")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

TYPES = ["2D CAD", "CAD", "CAM", "Tools", "Others"]
PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["Todo", "In Progress", "Review", "Testing", "Done", "Blocked", "Handoff"]
