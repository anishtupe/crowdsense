"""Minimal WebSocket connection manager for broadcasting incident updates
to connected dashboard clients. For multi-process deployments, back this
with Redis pub/sub instead of an in-memory list (each process subscribes
and re-broadcasts to its own local connections)."""
from __future__ import annotations

import json
from typing import List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message)
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                stale.append(connection)
        for c in stale:
            self.disconnect(c)


manager = ConnectionManager()
