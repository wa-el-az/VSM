from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.database import get_db, get_transaction
from app.economics import economics
from app.models import AssetInfo, OrderCreate, OrderResponse, PortfolioItem
from app.routes.auth import get_current_user
from app.simulation import engine
from app.websocket_manager import manager

router = APIRouter()


@router.get("/assets", response_model=list[AssetInfo])
def list_assets() -> list[AssetInfo]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, symbol, name, sector, base_price, mu, sigma FROM assets WHERE is_active = 1"
        ).fetchall()
    return [AssetInfo(**dict(r)) for r in rows]


@router.get("/prices")
def get_prices() -> dict[str, float]:
    return engine.get_all_prices()


@router.get("/prices/{symbol}/history")
def price_history(symbol: str, limit: int = 500) -> list[dict]:
    with get_db() as conn:
        asset = conn.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,)).fetchone()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        rows = conn.execute(
            "SELECT timestamp, open, high, low, close, volume "
            "FROM asset_prices WHERE asset_id = ? ORDER BY timestamp DESC LIMIT ?",
            (asset["id"], limit),
        ).fetchall()

    return [dict(r) for r in reversed(rows)]


@router.post("/orders", response_model=OrderResponse)
def place_order(
    body: OrderCreate,
    user: Annotated[dict, Depends(get_current_user)],
) -> OrderResponse:
    with get_transaction() as conn:
        asset = conn.execute(
            "SELECT id, symbol FROM assets WHERE symbol = ? AND is_active = 1",
            (body.symbol,),
        ).fetchone()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        current_price = engine.get_price(body.symbol)
        if current_price is None:
            raise HTTPException(status_code=503, detail="Market not active")

        exec_price = body.limit_price if body.order_type == "limit" and body.limit_price else current_price
        total_cost = exec_price * body.quantity

        if body.side == "buy":
            tx_type = "limit" if body.order_type == "limit" else "buy"
            tax = economics.calculate_tax(total_cost, tx_type)
            required = total_cost + tax

            bal = conn.execute(
                "SELECT balance FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if bal["balance"] < required:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            conn.execute(
                "UPDATE users SET balance = balance - ? WHERE id = ?",
                (required, user["id"]),
            )
            conn.execute(
                "UPDATE users SET total_taxed = total_taxed + ? WHERE id = ?",
                (tax, user["id"]),
            )

            existing = conn.execute(
                "SELECT quantity, avg_cost FROM portfolios WHERE user_id = ? AND asset_id = ?",
                (user["id"], asset["id"]),
            ).fetchone()

            if existing:
                new_qty = existing["quantity"] + body.quantity
                new_avg = (
                    (existing["avg_cost"] * existing["quantity"]) + (exec_price * body.quantity)
                ) / new_qty
                conn.execute(
                    "UPDATE portfolios SET quantity = ?, avg_cost = ? WHERE user_id = ? AND asset_id = ?",
                    (new_qty, round(new_avg, 2), user["id"], asset["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO portfolios (user_id, asset_id, quantity, avg_cost) VALUES (?, ?, ?, ?)",
                    (user["id"], asset["id"], body.quantity, exec_price),
                )

            new_bal = conn.execute("SELECT balance FROM users WHERE id = ?", (user["id"],)).fetchone()
            conn.execute(
                "INSERT INTO ledger_entries (user_id, entry_type, amount, balance_after, description) "
                "VALUES (?, 'trade_debit', ?, ?, ?)",
                (user["id"], -required, new_bal["balance"], f"BUY {body.quantity} {body.symbol} @ {exec_price}"),
            )

        else:
            holding = conn.execute(
                "SELECT quantity FROM portfolios WHERE user_id = ? AND asset_id = ?",
                (user["id"], asset["id"]),
            ).fetchone()
            if not holding or holding["quantity"] < body.quantity:
                raise HTTPException(status_code=400, detail="Insufficient shares")

            tx_type = "limit" if body.order_type == "limit" else "sell"
            net, tax = economics.apply_trade_tax(conn, user["id"], total_cost, tx_type)

            conn.execute(
                "UPDATE users SET balance = balance + ? WHERE id = ?",
                (net, user["id"]),
            )

            new_qty = holding["quantity"] - body.quantity
            if new_qty == 0:
                conn.execute(
                    "DELETE FROM portfolios WHERE user_id = ? AND asset_id = ?",
                    (user["id"], asset["id"]),
                )
            else:
                conn.execute(
                    "UPDATE portfolios SET quantity = ? WHERE user_id = ? AND asset_id = ?",
                    (new_qty, user["id"], asset["id"]),
                )

            new_bal = conn.execute("SELECT balance FROM users WHERE id = ?", (user["id"],)).fetchone()
            conn.execute(
                "INSERT INTO ledger_entries (user_id, entry_type, amount, balance_after, description) "
                "VALUES (?, 'trade_credit', ?, ?, ?)",
                (user["id"], net, new_bal["balance"], f"SELL {body.quantity} {body.symbol} @ {exec_price}"),
            )

        cursor = conn.execute(
            "INSERT INTO orders (user_id, asset_id, side, order_type, quantity, limit_price, filled_quantity, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'filled')",
            (user["id"], asset["id"], body.side.value, body.order_type.value,
             body.quantity, body.limit_price, body.quantity),
        )
        order_id = cursor.lastrowid

    return OrderResponse(
        id=order_id,
        user_id=user["id"],
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        quantity=body.quantity,
        limit_price=body.limit_price,
        status="filled",
        created_at="",
    )


@router.get("/portfolio", response_model=list[PortfolioItem])
def get_portfolio(user: Annotated[dict, Depends(get_current_user)]) -> list[PortfolioItem]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT p.quantity, p.avg_cost, a.symbol, a.name "
            "FROM portfolios p JOIN assets a ON p.asset_id = a.id "
            "WHERE p.user_id = ? AND p.quantity > 0",
            (user["id"],),
        ).fetchall()

    items = []
    for r in rows:
        current = engine.get_price(r["symbol"]) or r["avg_cost"]
        pnl = (current - r["avg_cost"]) * r["quantity"]
        items.append(PortfolioItem(
            symbol=r["symbol"],
            name=r["name"],
            quantity=r["quantity"],
            avg_cost=round(r["avg_cost"], 2),
            current_price=round(current, 2),
            pnl=round(pnl, 2),
        ))
    return items


@router.get("/orders", response_model=list[OrderResponse])
def get_orders(user: Annotated[dict, Depends(get_current_user)]) -> list[OrderResponse]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT o.id, o.user_id, a.symbol, o.side, o.order_type, o.quantity, "
            "o.limit_price, o.status, o.created_at "
            "FROM orders o JOIN assets a ON o.asset_id = a.id "
            "WHERE o.user_id = ? ORDER BY o.created_at DESC LIMIT 50",
            (user["id"],),
        ).fetchall()

    return [OrderResponse(**dict(r)) for r in rows]


@router.get("/economy")
def economy_stats() -> dict:
    return economics.get_economy_stats()


@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str) -> None:
    from jose import jwt as jose_jwt
    try:
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = payload["sub"]
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "pong":
                continue
            elif msg_type == "subscribe":
                symbol = data.get("symbol", "")
                if symbol:
                    manager.subscribe(user_id, symbol)
            elif msg_type == "unsubscribe":
                symbol = data.get("symbol", "")
                if symbol:
                    manager.unsubscribe(user_id, symbol)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
