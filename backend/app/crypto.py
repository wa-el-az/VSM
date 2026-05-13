from __future__ import annotations

import hashlib
import hmac
import random
import time
import uuid

from app.config import settings
from app.models import TaskTier

_TIER_CONFIG = {
    TaskTier.EASY: {
        "reward_min": settings.task_tier1_reward_min,
        "reward_max": settings.task_tier1_reward_max,
        "cooldown": settings.task_tier1_cooldown,
    },
    TaskTier.MEDIUM: {
        "reward_min": settings.task_tier2_reward_min,
        "reward_max": settings.task_tier2_reward_max,
        "cooldown": settings.task_tier2_cooldown,
    },
    TaskTier.HARD: {
        "reward_min": settings.task_tier3_reward_min,
        "reward_max": settings.task_tier3_reward_max,
        "cooldown": settings.task_tier3_cooldown,
    },
}


def _sign(payload: str) -> str:
    return hmac.new(
        settings.hmac_secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_task(user_id: int, tier: TaskTier) -> dict:
    """Generate a cryptographically signed math challenge."""
    task_id = str(uuid.uuid4())
    nonce = str(uuid.uuid4())
    expires = time.time() + settings.task_expiration_seconds

    if tier == TaskTier.EASY:
        a, b = random.randint(10, 999), random.randint(10, 999)
        op = random.choice(["+", "-", "*"])
        question = f"{a} {op} {b}"
        answer = eval(question)  # noqa: S307 — controlled input, no user data
    elif tier == TaskTier.MEDIUM:
        a = random.randint(2, 12)
        b = random.randint(1, 50)
        c = random.randint(1, 200)
        answer = (c - b) / a
        question = f"Solve for x: {a}x + {b} = {c}"
    else:
        a = random.randint(2, 8)
        b = random.randint(1, 100)
        answer = a * b ** (a - 1)
        question = f"Find d/dx of x^{a} at x = {b}"

    sig_payload = f"{task_id}|{nonce}|{user_id}|{expires}"
    signature = _sign(sig_payload)

    return {
        "task_id": task_id,
        "tier": tier.value,
        "question": question,
        "answer": float(answer),
        "nonce": nonce,
        "signature": signature,
        "expires": expires,
        "reward": random.randint(
            _TIER_CONFIG[tier]["reward_min"],
            _TIER_CONFIG[tier]["reward_max"],
        ),
    }


def verify_submission(
    task_id: str,
    nonce: str,
    user_id: int,
    expires: float,
    submitted_sig: str,
) -> bool:
    """Verify HMAC signature and expiration."""
    if time.time() > expires:
        return False

    sig_payload = f"{task_id}|{nonce}|{user_id}|{expires}"
    expected = _sign(sig_payload)
    return hmac.compare_digest(submitted_sig, expected)


def get_reward_range(tier: TaskTier) -> tuple[int, int]:
    cfg = _TIER_CONFIG[tier]
    return cfg["reward_min"], cfg["reward_max"]


def get_cooldown(tier: TaskTier) -> int:
    return _TIER_CONFIG[tier]["cooldown"]
