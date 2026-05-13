from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.database import get_db
from app.models import TokenResponse, UserLogin, UserPublic, UserRegister

router = APIRouter()
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer()


def _create_token(user_id: int, username: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)
    payload = {"sub": str(user_id), "username": username, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)]) -> dict:
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
        username = payload["username"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    with get_db() as conn:
        row = conn.execute("SELECT id, username, balance FROM users WHERE id = ?", (user_id,)).fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return {"id": row["id"], "username": row["username"], "balance": row["balance"]}


@router.post("/register", response_model=TokenResponse)
def register(body: UserRegister) -> TokenResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        hashed = _pwd_ctx.hash(body.password)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, balance) VALUES (?, ?, ?)",
            (body.username, hashed, settings.initial_player_balance),
        )
        conn.commit()
        user_id = cursor.lastrowid

    token = _create_token(user_id, body.username)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin) -> TokenResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (body.username,),
        ).fetchone()

    if not row or not _pwd_ctx.verify(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = _create_token(row["id"], row["username"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[dict, Depends(get_current_user)]) -> UserPublic:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, balance, created_at FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()

    return UserPublic(
        id=row["id"],
        username=row["username"],
        balance=row["balance"],
        created_at=row["created_at"],
    )
