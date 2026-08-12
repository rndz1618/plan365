# Plan365 — lightweight image for SBC / low-RAM hosts
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAN365_DB=/data/plan365.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app ./app
COPY static ./static
COPY seed_demo.py .

RUN mkdir -p /data

EXPOSE 8000

# Single worker — fits 2GB RAM constraint
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
