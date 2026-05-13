from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ──

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TaskTier(int, Enum):
    EASY = 1
    MEDIUM = 2
    HARD = 3


class WSMessageType(str, Enum):
    PRICE_UPDATE = "price_update"
    ORDER_FILL = "order_fill"
    BALANCE_CHANGE = "balance_change"
    NEWS_EVENT = "news_event"
    PING = "ping"
    PONG = "pong"


# ── Auth ──

class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    balance: float
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Assets ──

class AssetInfo(BaseModel):
    id: int
    symbol: str
    name: str
    sector: str
    base_price: float
    mu: float
    sigma: float


class PriceBar(BaseModel):
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceUpdate(BaseModel):
    symbol: str
    price: float
    timestamp: float
    volume: float


# ── Orders & Trades ──

class OrderCreate(BaseModel):
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)


class OrderResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: float | None
    status: str
    created_at: str


class TradeRecord(BaseModel):
    id: int
    buyer_id: int
    seller_id: int
    asset_id: int
    symbol: str
    quantity: int
    price: float
    tax: float
    timestamp: str


# ── Portfolio ──

class PortfolioItem(BaseModel):
    symbol: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    pnl: float


# ── Tasks (Proof-of-Work Faucet) ──

class TaskRequest(BaseModel):
    tier: TaskTier


class TaskChallenge(BaseModel):
    task_id: str
    tier: TaskTier
    question: str
    nonce: str
    signature: str
    expires: float


class TaskSubmit(BaseModel):
    task_id: str
    nonce: str
    answer: float
    signature: str


class TaskResult(BaseModel):
    success: bool
    reward: float = 0.0
    new_balance: float = 0.0
    error: str | None = None


# ── Economics ──

class EconomyStats(BaseModel):
    total_supply: float
    total_faucet_output: float
    total_sink_drainage: float
    sink_coverage_ratio: float
    active_players: int
    current_tax_rates: dict[str, float]


# ── WebSocket Envelope ──

class WSMessage(BaseModel):
    type: WSMessageType
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    payload: dict
