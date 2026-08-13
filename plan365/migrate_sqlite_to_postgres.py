#!/usr/bin/env python3
"""Migrate Plan365 data from SQLite → PostgreSQL. See root migrate_sqlite_to_postgres.py for full docs."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent.parent / "migrate_sqlite_to_postgres.py"), run_name="__main__")
