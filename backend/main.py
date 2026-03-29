"""
SmartSpend - Application Entry Point (FIXED)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import login, expense, profile
from backend.notification_service import start_scheduler
from backend.calendar_service import create_recurring_daily_reminder
from backend.cache import cached_read          # ← shared cache (no circular import)

import os
import logging

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(__file__)
USERS_PATH    = os.path.join(BASE_DIR, "database", "users.json")
EXPENSES_PATH = os.path.join(BASE_DIR, "database", "expenses.json")
PROFILES_PATH = os.path.join(BASE_DIR, "database", "profiles.json")


# ── Data helpers (passed into scheduler) ──────────────────────────────────────

def get_all_users() -> list[dict]:
    try:
        users    = cached_read(USERS_PATH)
        profiles = cached_read(PROFILES_PATH)
    except Exception as exc:
        logger.error("get_all_users failed: %s", exc)
        return []

    profile_map = {p["username"]: p for p in profiles}
    result = []

    for u in users:
        username = u.get("username")
        email    = u.get("email")
        if not username or not email:
            continue

        profile = profile_map.get(username, {})
        income  = profile.get("income", {})
        amount  = (
            income.get("monthly_salary")
            or income.get("allowance")
            or 0
        )
        result.append({"username": username, "email": email, "income": amount})

    return result


def get_user_expenses(username: str, month: str) -> list[dict]:
    try:
        expenses = cached_read(EXPENSES_PATH)
    except Exception as exc:
        logger.error("get_user_expenses failed: %s", exc)
        return []

    return [
        e for e in expenses
        if e.get("username") == username and e.get("month") == month
    ]


# ── CORS ───────────────────────────────────────────────────────────────────────
_raw_origins    = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")]


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 SmartSpend starting up...")

    try:
        start_scheduler(get_all_users, get_user_expenses)
        logger.info("✅ Scheduler started.")
    except Exception as exc:
        logger.error("❌ Scheduler failed: %s", exc)

    try:
        created = create_recurring_daily_reminder()
        logger.info("✅ Calendar reminder %s.", "created" if created else "already exists — skipped")
    except Exception as exc:
        logger.warning("⚠️  Calendar setup failed (non-fatal): %s", exc)

    logger.info("✅ SmartSpend ready.")
    yield
    logger.info("🛑 SmartSpend shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "SmartSpend API",
    version     = "1.0.0",
    description = "Personal expense tracking with smart notifications.",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ALLOWED_ORIGINS,
    allow_methods     = ["GET", "POST", "PUT", "DELETE"],
    allow_headers     = ["Authorization", "Content-Type"],
    allow_credentials = True,
)

app.include_router(login.router,   tags=["Auth"])
app.include_router(expense.router, tags=["Expenses"])
app.include_router(profile.router, tags=["Profile"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "SmartSpend"}