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

TYPES = ["2D CAD", "CAD", "CAM", "Tools", "Others"]
PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["Todo", "In Progress", "Review", "Testing", "Done", "Blocked", "Handoff"]
