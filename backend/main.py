from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, List
import json
import uuid
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from executor import executor

app = FastAPI()

execution_pool = ThreadPoolExecutor(max_workers=3)

class CodeRunRequest(BaseModel):
    code: str

class Room:
    """
    Represents one collaborative editing session.
    Holds the shared document content, version, connected users, and
    now also each user's current cursor position.
    """

    def __init__(self, room_id: str):
        self.room_id = room_id
        self.content: str = ""
        self.version: int = 0
        self.connections: List[dict] = []  # [{"ws", "user_id", "username", "cursor_pos"}]
        self.last_edit_time: float = 0
        self.last_editor: str = ""

    def get_usernames(self) -> List[str]:
        return [c["username"] for c in self.connections]

    def get_cursors(self) -> List[dict]:
        """Returns cursor positions of everyone except None, for broadcasting."""
        return [
            {"user_id": c["user_id"], "username": c["username"], "cursor_pos": c["cursor_pos"]}
            for c in self.connections
            if c["cursor_pos"] is not None
        ]


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def get_or_create_room(self, room_id: str) -> Room:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id)
        return self.rooms[room_id]

    async def connect(self, room_id: str, websocket: WebSocket, username: str) -> str:
        await websocket.accept()
        room = self.get_or_create_room(room_id)

        user_id = str(uuid.uuid4())[:8]
        room.connections.append({
            "ws": websocket, "user_id": user_id, "username": username, "cursor_pos": None
        })
        print(f"[JOIN] {username} ({user_id}) joined room '{room_id}'. Total: {len(room.connections)}")

        await websocket.send_text(json.dumps({
            "type": "sync",
            "content": room.content,
            "version": room.version,
            "online_users": room.get_usernames(),
            "cursors": room.get_cursors()
        }))

        await self.broadcast(room_id, {
            "type": "user_joined",
            "user_id": user_id,
            "username": username,
            "online_users": room.get_usernames()
        }, sender=websocket)

        return user_id

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id not in self.rooms:
            return None
        room = self.rooms[room_id]
        leaving_user = None
        for entry in room.connections:
            if entry["ws"] == websocket:
                leaving_user = entry
                break
        if leaving_user:
            room.connections.remove(leaving_user)
            print(f"[LEAVE] {leaving_user['username']} left room '{room_id}'. Remaining: {len(room.connections)}")
        return leaving_user

    async def apply_edit(self, room_id: str, content: str, editor_user_id: str, editor_username: str):
        """Last-write-wins update to the shared document (see Day 3 notes)."""
        room = self.get_or_create_room(room_id)
        room.content = content
        room.version += 1
        room.last_edit_time = time.time()
        room.last_editor = editor_username

        await self.broadcast(room_id, {
            "type": "edit",
            "content": content,
            "version": room.version,
            "from_user_id": editor_user_id,
            "from_username": editor_username
        }, sender=None)

    async def update_cursor(self, room_id: str, user_id: str, username: str, cursor_pos: int):
        """
        NEW in Day 4: track and broadcast where each user's cursor is.
        This is sent much more often than edits (every click/arrow key), so we
        keep it lightweight and DON'T bump the document version for cursor moves.
        """
        room = self.get_or_create_room(room_id)
        for entry in room.connections:
            if entry["user_id"] == user_id:
                entry["cursor_pos"] = cursor_pos
                break

        await self.broadcast(room_id, {
            "type": "cursor",
            "user_id": user_id,
            "username": username,
            "cursor_pos": cursor_pos
        }, sender=None)

    async def handle_run_code(self, room_id: str, code: str, requester_username: str):
        """
        Runs the current code via Docker (blocking call) in a background thread,
        so we don't freeze the WebSocket event loop for other rooms/users.
        Broadcasts "running" status immediately, then the result once done.
        """
        # Let everyone in the room know execution has started
        await self.broadcast(room_id, {
            "type": "run_status",
            "status": "running",
            "requested_by": requester_username
        }, sender=None)

        loop = asyncio.get_event_loop()
        # Run the blocking Docker subprocess call in a separate thread
        result = await loop.run_in_executor(execution_pool, executor.run_python_code, code)

        # Broadcast the final result to everyone in the room
        await self.broadcast(room_id, {
            "type": "run_result",
            "requested_by": requester_username,
            **result
        }, sender=None)

    async def broadcast(self, room_id: str, message: dict, sender: WebSocket = None):
        if room_id not in self.rooms:
            return
        payload = json.dumps(message)
        for entry in self.rooms[room_id].connections:
            if entry["ws"] != sender:
                await entry["ws"].send_text(payload)


manager = RoomManager()


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Collab code editor backend running"}

@app.post("/run-code")
def run_code(request: CodeRunRequest):
    """
    Executes submitted Python code inside an isolated Docker sandbox
    and returns stdout/stderr. This runs synchronously for now (Day 6);
    Day 8-9 will connect this to WebSocket for live streaming output.
    """
    result = executor.run_python_code(request.code)
    return result

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    username = websocket.query_params.get("username", "Anonymous")
    user_id = await manager.connect(room_id, websocket, username)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                data = {"type": "edit", "content": raw_data}

            msg_type = data.get("type")

            if msg_type == "edit":
                await manager.apply_edit(room_id, data.get("content", ""), user_id, username)
            elif msg_type == "cursor":
                await manager.update_cursor(room_id, user_id, username, data.get("cursor_pos", 0))
            elif msg_type == "run":
                # Run the currently submitted code and broadcast results to the room.
                # Fire-and-forget via create_task so this doesn't block receiving
                # further messages (like cursor moves) while code is executing.
                code_to_run = data.get("code", "")
                asyncio.create_task(manager.handle_run_code(room_id, code_to_run, username))

    except WebSocketDisconnect:
        leaving_user = manager.disconnect(room_id, websocket)
        if leaving_user:
            room = manager.rooms.get(room_id)
            online = room.get_usernames() if room else []
            await manager.broadcast(room_id, {
                "type": "user_left",
                "user_id": leaving_user["user_id"],
                "username": leaving_user["username"],
                "online_users": online
            })