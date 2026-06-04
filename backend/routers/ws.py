from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.ws import manager


router = APIRouter()


@router.websocket("/ws/tasks")
async def ws_tasks(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # We accept any message (could be {subscribe: task_id}) but currently broadcast all events
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
