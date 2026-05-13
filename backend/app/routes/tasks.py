from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.crypto import generate_task, verify_submission
from app.database import get_db, get_transaction
from app.economics import economics
from app.models import TaskChallenge, TaskRequest, TaskResult, TaskSubmit, TaskTier
from app.routes.auth import get_current_user

router = APIRouter()

_pending_tasks: dict[str, dict] = {}


@router.post("/request", response_model=TaskChallenge)
def request_task(
    body: TaskRequest,
    user: Annotated[dict, Depends(get_current_user)],
) -> TaskChallenge:
    task_data = generate_task(user["id"], body.tier)

    _pending_tasks[task_data["task_id"]] = {
        "answer": task_data["answer"],
        "reward": task_data["reward"],
        "user_id": user["id"],
        "tier": body.tier.value,
        "expires": task_data["expires"],
    }

    return TaskChallenge(
        task_id=task_data["task_id"],
        tier=body.tier,
        question=task_data["question"],
        nonce=task_data["nonce"],
        signature=task_data["signature"],
        expires=task_data["expires"],
    )


@router.post("/submit", response_model=TaskResult)
def submit_task(
    body: TaskSubmit,
    user: Annotated[dict, Depends(get_current_user)],
) -> TaskResult:
    pending = _pending_tasks.pop(body.task_id, None)
    if not pending:
        return TaskResult(success=False, error="Task not found or already submitted")

    if pending["user_id"] != user["id"]:
        return TaskResult(success=False, error="Task not assigned to you")

    if time.time() > pending["expires"]:
        return TaskResult(success=False, error="Task expired")

    if not verify_submission(
        body.task_id, body.nonce, user["id"], pending["expires"], body.signature
    ):
        return TaskResult(success=False, error="invalid_submission")

    tolerance = 0.01
    if abs(body.answer - pending["answer"]) > tolerance:
        return TaskResult(success=False, error="Incorrect answer")

    with get_transaction() as conn:
        already = conn.execute(
            "SELECT task_id FROM completed_tasks WHERE task_id = ?", (body.task_id,)
        ).fetchone()
        if already:
            return TaskResult(success=False, error="Task already completed")

        reward = pending["reward"]
        new_balance = economics.credit_faucet(
            conn, user["id"], reward,
            f"PoW Tier {pending['tier']} reward: {reward}",
        )

        conn.execute(
            "INSERT INTO completed_tasks (task_id, user_id, tier, reward) VALUES (?, ?, ?, ?)",
            (body.task_id, user["id"], pending["tier"], reward),
        )

    return TaskResult(success=True, reward=reward, new_balance=new_balance)
