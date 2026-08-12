"""In-memory pub/sub for SSE real-time updates (single-worker, low RAM)."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional, Set


class EventBroker:
    """Fan-out async queues to connected SSE clients. No Redis required."""

    def __init__(self, max_queue: int = 32):
        self._subs: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._max_queue = max_queue
        self._seq = 0

    @property
    def connections(self) -> int:
        return len(self._subs)

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        async with self._lock:
            self._subs.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subs.discard(q)

    async def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._seq += 1
        payload = {
            "id": self._seq,
            "type": event_type,
            "ts": time.time(),
            "data": data or {},
        }
        dead: list = []
        async with self._lock:
            targets = list(self._subs)
        for q in targets:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # drop oldest then push — keep client moving
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.append(q)
        for q in dead:
            await self.unsubscribe(q)


broker = EventBroker()


def publish_sync(event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
    """Schedule publish from sync route handlers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broker.publish(event_type, data))
        else:
            loop.run_until_complete(broker.publish(event_type, data))
    except RuntimeError:
        # no loop (e.g. during import) — ignore
        pass


def sse_encode(payload: Dict[str, Any]) -> str:
    eid = payload.get("id", 0)
    etype = payload.get("type", "message")
    body = json.dumps(payload, default=str)
    return f"id: {eid}\nevent: {etype}\ndata: {body}\n\n"
