from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import get_db, init_db
from app.economics import economics
from app.news_engine import news_engine
from app.routes import auth, market, tasks
from app.simulation import engine
from app.websocket_manager import manager

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend_static"
if not FRONTEND_DIR.is_dir():
    FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

_sim_task: asyncio.Task | None = None


def _load_assets_into_engine() -> None:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT symbol, base_price, mu, sigma FROM assets WHERE is_active = 1"
        ).fetchall()
    for r in rows:
        engine.register_asset(r["symbol"], r["base_price"], r["mu"], r["sigma"])
    logger.info("Registered %d assets with simulation engine", len(rows))


async def _simulation_loop() -> None:
    tick_interval = settings.simulation_tick_interval
    ohlc_save_every = 60
    last_ohlc_save = time.time()

    while True:
        try:
            price_updates = engine.tick()

            for symbol, update in price_updates.items():
                await manager.broadcast(symbol, {
                    "type": "price_update",
                    "timestamp": update["timestamp"],
                    "payload": update,
                })

            triggered = news_engine.roll_events()
            for event in triggered:
                await manager.broadcast_all({
                    "type": "news_event",
                    "timestamp": time.time(),
                    "payload": {"name": event["name"], "event_id": event["event_id"]},
                })

            now = time.time()
            if now - last_ohlc_save >= ohlc_save_every:
                _save_ohlc_snapshot()
                economics.auto_adjust_rates()
                last_ohlc_save = now

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Simulation tick error")

        await asyncio.sleep(tick_interval)


def _save_ohlc_snapshot() -> None:
    with get_db() as conn:
        assets = conn.execute("SELECT id, symbol FROM assets WHERE is_active = 1").fetchall()
        now = time.time()
        for asset in assets:
            bar = engine.get_ohlc_and_reset(asset["symbol"])
            if bar:
                conn.execute(
                    "INSERT INTO asset_prices (asset_id, timestamp, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (asset["id"], now, bar["open"], bar["high"], bar["low"], bar["close"], bar["volume"]),
                )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    _load_assets_into_engine()
    await manager.connect_redis()
    global _sim_task
    _sim_task = asyncio.create_task(_simulation_loop())
    logger.info("Simulation loop started (tick=%.1fs)", settings.simulation_tick_interval)
    yield
    if _sim_task:
        _sim_task.cancel()
        try:
            await _sim_task
        except asyncio.CancelledError:
            pass
    await manager.disconnect_redis()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIR.is_dir():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
