from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with room-based subscriptions and Redis Pub/Sub bridge."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._rooms: dict[str, set[str]] = {}
        self._user_rooms: dict[str, set[str]] = {}
        self._redis = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None

    async def connect_redis(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            self._pubsub = self._redis.pubsub()
            channel = f"{settings.redis_channel_prefix}.updates"
            await self._pubsub.subscribe(channel)
            self._listener_task = asyncio.create_task(self._redis_listener())
            logger.info("Redis Pub/Sub connected on channel: %s", channel)
        except Exception as e:
            logger.warning("Redis unavailable, running without pub/sub: %s", e)
            self._redis = None

    async def disconnect_redis(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()

    async def _redis_listener(self) -> None:
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    room = data.get("room", "__broadcast__")
                    await self._broadcast_local(room, data.get("payload", {}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Redis listener error: %s", e)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id] = websocket
        self._user_rooms[user_id] = set()
        logger.info("WS connected: %s (total: %d)", user_id, len(self._connections))

    def disconnect(self, user_id: str) -> None:
        self._connections.pop(user_id, None)
        for room in self._user_rooms.pop(user_id, set()):
            self._rooms.get(room, set()).discard(user_id)
        logger.info("WS disconnected: %s (total: %d)", user_id, len(self._connections))

    def subscribe(self, user_id: str, room: str) -> None:
        self._rooms.setdefault(room, set()).add(user_id)
        self._user_rooms.setdefault(user_id, set()).add(room)

    def unsubscribe(self, user_id: str, room: str) -> None:
        self._rooms.get(room, set()).discard(user_id)
        self._user_rooms.get(user_id, set()).discard(room)

    async def send_personal(self, user_id: str, data: dict) -> None:
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(user_id)

    async def _broadcast_local(self, room: str, data: dict) -> None:
        if room == "__broadcast__":
            targets = list(self._connections.keys())
        else:
            targets = list(self._rooms.get(room, set()))

        tasks = []
        for uid in targets:
            ws = self._connections.get(uid)
            if ws:
                tasks.append(ws.send_json(data))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for uid, result in zip(targets, results):
                if isinstance(result, Exception):
                    self.disconnect(uid)

    async def broadcast(self, room: str, data: dict) -> None:
        """Broadcast via Redis if available, otherwise local only."""
        if self._redis:
            channel = f"{settings.redis_channel_prefix}.updates"
            payload = json.dumps({"room": room, "payload": data})
            await self._redis.publish(channel, payload)
        else:
            await self._broadcast_local(room, data)

    async def broadcast_all(self, data: dict) -> None:
        await self.broadcast("__broadcast__", data)

    async def heartbeat(self, user_id: str) -> None:
        await self.send_personal(user_id, {
            "type": "ping",
            "timestamp": time.time(),
            "payload": {},
        })

    async def send_to_user(self, user_id: str, data: dict) -> None:
        """Alias for send_personal for consistency."""
        await self.send_personal(user_id, data)

    def is_active(self, user_id: str) -> bool:
        return user_id in self._connections

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
