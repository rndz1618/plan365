"""
Plan365 - Lightweight Project & Task Manager
Optimized for Linux SBC 2GB RAM
Modular FastAPI + SQLite + JWT
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, BASE_DIR
from app.database import init_db
from app.routers import auth_routes, projects, tasks, dependencies, settings, export

init_db()

app = FastAPI(title="Plan365", version="1.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(dependencies.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(export.router, prefix="/api")

# Static assets (css/js) — HTML shell at /
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    index = BASE_DIR / "static" / "index.html"
    if not index.exists():
        index = BASE_DIR / "index.html"
    return FileResponse(index)


@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1, log_level="info", reload=False)
