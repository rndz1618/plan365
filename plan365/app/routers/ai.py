"""AI integration: snapshot, local planning analysis, optional LLM chat."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import current_user, require_admin
from app.database import db
from app.ai_engine import analyze_snapshot, build_snapshot, chat_with_llm, get_ai_settings

router = APIRouter(tags=["ai"])


class AiChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    project_id: Optional[int] = None


class AiSettingsIn(BaseModel):
    ai_enabled: Optional[bool] = None
    ai_api_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_system_prompt: Optional[str] = None


@router.get("/ai/sync")
async def ai_sync(u=Depends(current_user)):
    """Package active workspace for AI agents / external automation."""
    with db() as c:
        return build_snapshot(c, u)


@router.get("/ai/analyze")
async def ai_analyze(u=Depends(current_user)):
    """Offline planning analysis: risks, capacity, focus queue."""
    with db() as c:
        snap = build_snapshot(c, u)
        return analyze_snapshot(snap)


@router.post("/ai/chat")
async def ai_chat(body: AiChatIn, u=Depends(current_user)):
    """
    Ask the planning assistant.
    Uses local heuristics always; calls OpenAI-compatible API when enabled + key set.
    """
    with db() as c:
        snap = build_snapshot(c, u)
        if body.project_id is not None:
            snap["projects"] = [p for p in snap["projects"] if p["id"] == body.project_id]
        analysis = analyze_snapshot(snap)
        settings = get_ai_settings(c)
    result = await chat_with_llm(
        settings=settings,
        message=body.message.strip(),
        snapshot=snap,
        analysis=analysis,
    )
    return result


@router.get("/ai/settings")
async def ai_settings_get(u=Depends(current_user)):
    with db() as c:
        s = get_ai_settings(c)
    # never expose full key
    key = s.get("ai_api_key") or ""
    return {
        "ai_enabled": (s.get("ai_enabled") or "false").lower() in ("1", "true", "yes"),
        "ai_api_url": s.get("ai_api_url") or "",
        "ai_model": s.get("ai_model") or "",
        "ai_system_prompt": s.get("ai_system_prompt") or "",
        "ai_api_key_set": bool(key),
        "ai_api_key_masked": ("••••" + key[-4:]) if len(key) >= 4 else ("••••" if key else ""),
    }


@router.put("/ai/settings")
async def ai_settings_put(body: AiSettingsIn, u=Depends(require_admin)):
    from datetime import datetime

    with db() as c:
        mapping = {}
        if body.ai_enabled is not None:
            mapping["ai_enabled"] = "true" if body.ai_enabled else "false"
        if body.ai_api_url is not None:
            mapping["ai_api_url"] = body.ai_api_url.strip()
        if body.ai_model is not None:
            mapping["ai_model"] = body.ai_model.strip()
        if body.ai_system_prompt is not None:
            mapping["ai_system_prompt"] = body.ai_system_prompt.strip()
        if body.ai_api_key is not None and body.ai_api_key.strip() and body.ai_api_key.strip() != "••••":
            # ignore placeholder
            if not body.ai_api_key.startswith("••••"):
                mapping["ai_api_key"] = body.ai_api_key.strip()
        now = datetime.utcnow().isoformat()
        for k, v in mapping.items():
            c.execute(
                """INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at,
                   updated_by=excluded.updated_by""",
                (k, v, now, u["id"]),
            )
        s = get_ai_settings(c)
    return {
        "ok": True,
        "ai_enabled": (s.get("ai_enabled") or "false").lower() in ("1", "true", "yes"),
        "ai_api_url": s.get("ai_api_url") or "",
        "ai_model": s.get("ai_model") or "",
        "ai_api_key_set": bool(s.get("ai_api_key")),
    }
