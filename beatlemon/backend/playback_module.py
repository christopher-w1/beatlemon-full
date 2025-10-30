import asyncio
from fastapi import WebSocket
from typing import Dict, List, Optional
import json
import time


class PlaybackChannel:
    def __init__(self, owner_email: str, playlist: List[str]):
        self.owner = owner_email
        self.playlist = playlist
        self.current_index = 0
        self.start_time = None  # when the current song started
        self.position = 0.0     # last known playback position in seconds
        self.listeners: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    @property
    def current_song(self):
        if 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None

    async def join(self, email: str, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.listeners[email] = ws
        await self.broadcast(f"{email} joined playback")

        # initial sync
        await self.send_state(ws)

    async def leave(self, email: str):
        async with self.lock:
            if email in self.listeners:
                del self.listeners[email]
        await self.broadcast(f"{email} left playback")

    async def broadcast(self, message: str, data: Optional[dict] = None):
        payload = {"type": "info", "message": message}
        if data:
            payload.update(data)
        msg = json.dumps(payload)
        async with self.lock:
            for ws in list(self.listeners.values()):
                try:
                    await ws.send_text(msg)
                except:
                    pass  # ignore send errors

    async def send_state(self, ws: WebSocket):
        """Sends the current playback state to a single client."""
        await ws.send_json({
            "type": "state",
            "song": self.current_song,
            "index": self.current_index,
            "position": self.get_position()
        })

    def get_position(self) -> float:
        """Calculates estimated position since last start."""
        if self.start_time is None:
            return self.position
        return self.position + (time.time() - self.start_time)

    async def handle_message(self, email: str, data: dict):
        """Processes messages from clients."""
        t = data.get("type")
        if t == "position_update":
            async with self.lock:
                self.position = data.get("position", 0.0)
                self.start_time = time.time()
        elif t == "song_finished":
            await self.handle_song_finished(email)
        else:
            await self.broadcast(f"{email}: {data}")

    async def handle_song_finished(self, email: str):
        await self.broadcast(f"{email} finished song")
        # TODO: wait for majority of listeners to finish?
        if email == self.owner:
            # Assume owner controls playback
            self.current_index += 1
            self.position = 0.0
            self.start_time = None
            await self.broadcast("Next song", {"song": self.current_song})


class PlaybackModule:
    """Manages multiple playback channels."""
    def __init__(self):
        self.channels: Dict[str, PlaybackChannel] = {}
        self.lock = asyncio.Lock()

    async def create_channel(self, owner_id: str, playlist: List[str]) -> PlaybackChannel:
        async with self.lock:
            if owner_id in self.channels:
                raise ValueError("Channel already exists")
            channel = PlaybackChannel(owner_id, playlist)
            self.channels[owner_id] = channel
            return channel

    async def get_channel(self, owner_email: str) -> Optional[PlaybackChannel]:
        async with self.lock:
            return self.channels.get(owner_email)

    async def remove_channel(self, owner_email: str):
        async with self.lock:
            if owner_email in self.channels:
                del self.channels[owner_email]
