"""
SmartSpend - Expense Router (FIXED)
- Cache invalidation after every write
- Once-per-month notification flags
- Full error handling
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.utils.file_handler import read_json, write_json
from backend.cache import cached_read, invalidate
from typing import Optional
from datetime import datetime, date
from backend.notification_service import (
    notify_expense_added,
    notify_budget_exceeded,
    notify_budget_warning,
    notify_month_end,
)
from backend.config import BUDGET_LIMIT
from backend.calendar_service import (
    remove_today_reminder,
    create_streak_notification,
    create_budget_warning,
    create_budget_exceeded_alert,
    create_month_end_reminder,
)

import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(__file__))
DB_PATH    = os.path.join(BASE_DIR, "database", "expenses.json")
USERS_PATH = os.path.join(BASE_DIR, "database", "users.json")
FLAGS_PATH = os.path.join(BASE_DIR, "database", "notification_flags.json")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
for _path, _default in [(DB_PATH, []), (FLAGS_PATH, {})]:
    if not os.path.exists(_path):
        write_json(_path, _default)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flag_key(username: str, flag: str, period: str) -> str:
    return f"{username}:{flag}:{period}"

def _is_flagged(flags: dict, key: str) -> bool:
    return flags.get(key, False)

def _set_flag(flags: dict, key: str) -> dict:
    flags[key] = True
    return flags

def _calculate_streak(expenses: list, username: str) -> int:
    unique_dates: set[str] = set()
    for e in expenses:
        if e.get("username") != username:
            continue
        try:
            unique_dates.add(e["created_at"][:10])
        except (KeyError, TypeError):
            continue

    today  = date.today()
    streak = 0
    for i, d_str in enumerate(sorted(unique_dates, reverse=True)):
        try:
            d_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            break
        if (today - d_date).days == i:
            streak += 1
        else:
            break
    return streak


# ── Schema ─────────────────────────────────────────────────────────────────────

class ExpenseData(BaseModel):
    username:   str
    title:      str
    amount:     float
    category:   str
    created_at: Optional[str] = None
    month:      Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/add-expense")
def add_expense(data: ExpenseData):

    # 1. Persist ───────────────────────────────────────────────────────────────
    try:
        expenses = read_json(DB_PATH)
    except Exception as exc:
        logger.error("Read expenses failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not read expenses database.")

    now             = datetime.now()
    data.created_at = now.isoformat()
    data.month      = now.strftime("%Y-%m")
    expenses.append(data.dict())

    try:
        write_json(DB_PATH, expenses)
        invalidate(DB_PATH)                  # keep scheduler cache fresh
    except Exception as exc:
        logger.error("Write expenses failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not save expense.")

    logger.info("Expense added — user=%s amount=%.2f", data.username, data.amount)

    # 2. Notification flags ────────────────────────────────────────────────────
    try:
        flags = read_json(FLAGS_PATH)
    except Exception:
        flags = {}

    cur_month = now.strftime("%Y-%m")

    # 3. Remove today's calendar reminder ─────────────────────────────────────
    try:
        remove_today_reminder()
    except Exception as exc:
        logger.warning("remove_today_reminder: %s", exc)

    # 4. Streak ────────────────────────────────────────────────────────────────
    try:
        streak = _calculate_streak(expenses, data.username)
        if streak >= 2:
            create_streak_notification(streak)
    except Exception as exc:
        logger.warning("Streak: %s", exc)

    # 5. User email ────────────────────────────────────────────────────────────
    try:
        users      = cached_read(USERS_PATH)
        user       = next((u for u in users if u["username"] == data.username), None)
        user_email = user["email"] if user else None
    except Exception as exc:
        logger.warning("Load user failed: %s", exc)
        user_email = None

    if user_email:
        monthly_total = sum(
            e["amount"] for e in expenses
            if e.get("username") == data.username and e.get("month") == cur_month
        )

        # 5a. Expense added email (always) ─────────────────────────────────────
        try:
            notify_expense_added(user_email, {
                "title": data.title, "amount": data.amount, "category": data.category
            })
        except Exception as exc:
            logger.warning("notify_expense_added: %s", exc)

        # 5b. 80% warning — once per month ────────────────────────────────────
        warn_key = _flag_key(data.username, "budget_warning", cur_month)
        if BUDGET_LIMIT * 0.8 <= monthly_total < BUDGET_LIMIT and not _is_flagged(flags, warn_key):
            try:
                notify_budget_warning(user_email, monthly_total)
                create_budget_warning(monthly_total, BUDGET_LIMIT)
                flags = _set_flag(flags, warn_key)
            except Exception as exc:
                logger.warning("Budget warning: %s", exc)

        # 5c. Exceeded — once per month ───────────────────────────────────────
        exceeded_key = _flag_key(data.username, "budget_exceeded", cur_month)
        if monthly_total > BUDGET_LIMIT and not _is_flagged(flags, exceeded_key):
            try:
                notify_budget_exceeded(user_email, monthly_total)
                create_budget_exceeded_alert(monthly_total, BUDGET_LIMIT)
                flags = _set_flag(flags, exceeded_key)
            except Exception as exc:
                logger.warning("Budget exceeded: %s", exc)

        # 5d. Month-end — once per month ──────────────────────────────────────
        month_end_key = _flag_key(data.username, "month_end", cur_month)
        if now.day >= 25 and not _is_flagged(flags, month_end_key):
            try:
                notify_month_end(user_email, monthly_total)
                create_month_end_reminder()
                flags = _set_flag(flags, month_end_key)
            except Exception as exc:
                logger.warning("Month-end: %s", exc)

    # 6. Persist flags ─────────────────────────────────────────────────────────
    try:
        write_json(FLAGS_PATH, flags)
    except Exception as exc:
        logger.warning("Persist flags failed: %s", exc)

    return {"message": "Expense added successfully"}


@router.get("/expense/{username}")
def get_expenses(username: str):
    try:
        expenses = cached_read(DB_PATH)
    except Exception as exc:
        logger.error("Get expenses failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not retrieve expenses.")
    return {"expenses": [e for e in expenses if e.get("username") == username]}