# Deprecated: use the root-level script instead:
#   python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --wipe
# This nested path is kept only so existing docs/links do not 404.
raise SystemExit(
    "Use: python migrate_sqlite_to_postgres.py (from repo root). "
    "This nested wrapper is deprecated."
)
