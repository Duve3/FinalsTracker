import asyncio
import json
import aiohttp
from aiohttp import web, WSMsgType
from typing import Set, Optional
from ..log_config import get_logger

log = get_logger(__name__)


class LiveServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, dashboard_dir: Optional[str] = None):
        self.host = host
        self.port = port
        self.dashboard_dir = dashboard_dir
        self.app = web.Application()
        self.ws_clients: Set[web.WebSocketResponse] = set()
        self._message_callback = None
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/ws", self._websocket_handler)
        if self.dashboard_dir:
            self.app.router.add_static("/", self.dashboard_dir, show_index=True)

    def on_message(self, callback):
        self._message_callback = callback

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.ws_clients.add(ws)
        log.info("WebSocket client connected (%d total)", len(self.ws_clients))
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if self._message_callback:
                            await self._message_callback(data)
                    except json.JSONDecodeError:
                        log.warning("Invalid WebSocket message: %s", msg.data[:100])
                elif msg.type == WSMsgType.ERROR:
                    log.warning("WebSocket client error: %s", ws.exception())
                    break
        finally:
            self.ws_clients.discard(ws)
            log.info("WebSocket client disconnected (%d remaining)", len(self.ws_clients))
        return ws

    async def broadcast(self, data: dict):
        if not self.ws_clients:
            return
        message = json.dumps(data)
        dead = set()
        for ws in self.ws_clients:
            try:
                await ws.send_str(message)
            except (ConnectionResetError, ConnectionAbortedError) as e:
                log.debug("Removing dead WebSocket client: %s", e)
                dead.add(ws)
        if dead:
            self.ws_clients -= dead
            log.debug("Cleaned up %d dead WebSocket connection(s)", len(dead))
        log.debug("Broadcast '%s' to %d client(s)", data.get("type", "unknown"), len(self.ws_clients))

    async def send_match_update(self, match_data: dict):
        await self.broadcast({
            "type": "match_update",
            "data": match_data,
        })

    async def send_session_summary(self, summary: dict):
        await self.broadcast({
            "type": "session_summary",
            "data": summary,
        })

    async def send_match_history(self, history: list[dict]):
        await self.broadcast({
            "type": "match_history",
            "data": history,
        })

    async def send_career_stats(self, stats: dict):
        await self.broadcast({
            "type": "career_stats",
            "data": stats,
        })

    async def send_game_detected(self):
        await self.broadcast({
            "type": "game_detected",
            "data": {},
        })

    async def send_state_change(self, state: str):
        await self.broadcast({
            "type": "state_change",
            "data": {"state": state},
        })

    async def send_scoreboard_update(self, entries: list[dict]):
        await self.broadcast({
            "type": "scoreboard_update",
            "data": {"players": entries},
        })

    def start(self):
        log.info("Starting HTTP server on %s:%d", self.host, self.port)
        web.run_app(self.app, host=self.host, port=self.port, print=None)

    async def start_async(self):
        log.info("Starting async HTTP server on %s:%d", self.host, self.port)
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        return runner
