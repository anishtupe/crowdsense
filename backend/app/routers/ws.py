from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/incidents")
async def incidents_ws(websocket: WebSocket):
    """Dashboard clients connect here to receive live incident updates.
    Broadcast from anywhere in the backend with:

        from app.ws.manager import manager
        await manager.broadcast({"type": "incident_updated", "incident_id": "..."})
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from clients, but reading keeps
            # the connection alive and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
