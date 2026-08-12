"""Server-Sent Events stream for live UI updates."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt

from app.config import SECRET_KEY, ALGORITHM
from app.realtime import broker, sse_encode

router = APIRouter(tags=["realtime"])


def _user_from_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        if uid is None:
            return None
        return {"id": int(uid), "role": payload.get("role", "user")}
    except (JWTError, ValueError, TypeError):
        return None


@router.get("/events")
async def event_stream(
    request: Request,
    token: Optional[str] = Query(None, description="JWT (EventSource cannot set Authorization)"),
):
    """
    SSE endpoint. Browser EventSource connects with ?token=JWT.
    Events: task.*, project.*, dependency.*, ping
    """
    # Prefer query token (EventSource); fallback Authorization header
    auth = token
    if not auth:
        h = request.headers.get("authorization") or ""
        if h.lower().startswith("bearer "):
            auth = h[7:].strip()
    user = _user_from_token(auth or "")
    if not user:
        return StreamingResponse(
            iter([sse_encode({"id": 0, "type": "error", "data": {"message": "unauthorized"}})]),
            media_type="text/event-stream",
            status_code=401,
        )

    async def gen():
        q = await broker.subscribe()
        try:
            # hello
            yield sse_encode(
                {
                    "id": 0,
                    "type": "connected",
                    "data": {"user_id": user["id"], "connections": broker.connections},
                }
            )
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield sse_encode(msg)
                except asyncio.TimeoutError:
                    # keep-alive comment + soft ping event
                    yield ": keepalive\n\n"
                    yield sse_encode({"id": 0, "type": "ping", "data": {"connections": broker.connections}})
        finally:
            await broker.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events/status")
async def events_status():
    return {"connections": broker.connections, "transport": "sse"}
