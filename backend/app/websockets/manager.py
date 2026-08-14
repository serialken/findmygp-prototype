from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    """Tracks WebSocket connections grouped by an arbitrary room key
    (a booking id for tracking, a conversation id for messaging) and
    broadcasts JSON-serializable payloads to everyone in a room."""

    def __init__(self):
        self._rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self._rooms.setdefault(room, []).append(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        connections = self._rooms.get(room, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and room in self._rooms:
            del self._rooms[room]

    async def broadcast(self, room: str, payload: dict):
        dead = []
        for connection in self._rooms.get(room, []):
            try:
                await connection.send_json(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(room, connection)


tracking_manager = ConnectionManager()
messaging_manager = ConnectionManager()
