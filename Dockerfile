# Plan365 — PostgreSQL backend, optimized for low-RAM hosts
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app ./app
COPY static ./static
COPY seed_demo.py .
COPY migrate_sqlite_to_postgres.py .

EXPOSE 8000

# Single worker — SSE in-memory + low RAM
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
