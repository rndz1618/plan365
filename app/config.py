"""Plan365 configuration constants — PostgreSQL only."""
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

# PostgreSQL is required
#   PLAN365_DATABASE_URL=postgresql://user:pass@host:5432/plan365
DATABASE_URL = (
    os.environ.get("PLAN365_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or ""
).strip()

# Compatibility alias (always postgresql)
DB_BACKEND = "postgresql"

TYPES = ["2D CAD", "CAD", "CAM", "Tools", "Others"]
PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["Todo", "In Progress", "Review", "Testing", "Done", "Blocked", "Handoff"]
PROJECT_STATUSES = ["Active", "On Hold", "Completed", "Archived"]
