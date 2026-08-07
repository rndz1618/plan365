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
from app.routers import auth_routes, projects, tasks, dependencies, settings, export, dashboard, realtime, ai as ai_routes

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
app.include_router(dashboard.router, prefix="/api")
app.include_router(realtime.router, prefix="/api")
app.include_router(ai_routes.router, prefix="/api")

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    index = BASE_DIR / "static" / "index.html"
    if not index.exists():
        index = BASE_DIR / "index.html"
    return FileResponse(index)


@app.get("/diag")
async def diag():
    from fastapi.responses import HTMLResponse
    from app.config import STATIC_DIR, BASE_DIR
    files = {
        "index": (STATIC_DIR / "index.html").exists() or (BASE_DIR / "index.html").exists(),
        "app.js": (STATIC_DIR / "js" / "app.js").exists(),
        "alpine.min.js": (STATIC_DIR / "js" / "alpine.min.js").exists(),
        "deps.js": (STATIC_DIR / "js" / "deps.js").exists(),
        "gantt.js": (STATIC_DIR / "js" / "gantt.js").exists(),
        "app.css": (STATIC_DIR / "css" / "app.css").exists(),
    }
    rows = "".join(f"<li>{k}: <b>{'OK' if v else 'MISSING'}</b></li>" for k, v in files.items())
    html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>Plan365 diag</title></head>
<body style=\"font:16px system-ui;padding:2rem;background:#dce3e3\">
<h1>Plan365 diagnostics</h1>
<p>If you see this page, HTTP works. Open the home page after fixing any MISSING files.</p>
<ul>{rows}</ul>
<p><a href=\"/\">Go to app</a> · <a href=\"/static/js/app.js\">app.js</a> · <a href=\"/static/js/alpine.min.js\">alpine</a></p>
</body></html>"""
    return HTMLResponse(html)


@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1, log_level="info", reload=False)
