"""
SmartSpend - Smart Calendar Service (FINAL)
"""

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
import os
import pickle
import calendar
import logging

logger = logging.getLogger(__name__)

SCOPES         = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE       = "Asia/Kolkata"
TZ_OFFSET      = timedelta(hours=5, minutes=30)
SMARTSPEND_TAG = "smartspend-auto"

BASE_DIR   = os.path.dirname(__file__)
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.pickle")


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_calendar_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "rb") as f:
                creds = pickle.load(f)
        except Exception as exc:
            logger.warning("Could not load token file: %s", exc)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                logger.error("Token refresh failed: %s", exc)
                raise RuntimeError("Google token refresh failed. Re-authenticate.") from exc
        else:
            if os.environ.get("HEADLESS", "false").lower() == "true":
                raise RuntimeError(
                    "No valid Google token found and HEADLESS=true. "
                    "Run authenticate_locally() on a machine with a browser first."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        try:
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        except Exception as exc:
            logger.warning("Could not persist token: %s", exc)

    return build("calendar", "v3", credentials=creds)


def authenticate_locally():
    """One-time browser auth to generate token.pickle."""
    flow  = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)
    logger.info("token.pickle saved.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt(dt: datetime) -> str:
    """Format datetime for Google Calendar — no microseconds."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

def _local_now() -> datetime:
    return datetime.now()

def _ist_to_utc_z(dt: datetime) -> str:
    """Convert naive IST datetime → UTC 'Z' string for API queries."""
    return (dt - TZ_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ")

def _build_event(summary: str, description: str, start: datetime,
                 duration_minutes: int = 30, extra: dict | None = None) -> dict:
    end   = start + timedelta(minutes=duration_minutes)
    event = {
        "summary":     summary,
        "description": description,
        "start":       {"dateTime": _fmt(start), "timeZone": TIMEZONE},
        "end":         {"dateTime": _fmt(end),   "timeZone": TIMEZONE},
        "extendedProperties": {"private": {"source": SMARTSPEND_TAG}},
    }
    if extra:
        event.update(extra)
    return event

def _insert_event(event: dict) -> bool:
    try:
        service = get_calendar_service()
        service.events().insert(calendarId="primary", body=event).execute()
        logger.info("Calendar event created: %s", event.get("summary"))
        return True
    except Exception as exc:
        logger.error("Failed to create event '%s': %s", event.get("summary"), exc)
        return False


# ── Public API ─────────────────────────────────────────────────────────────────

def create_recurring_daily_reminder() -> bool:
    """
    Create a recurring 8 PM daily reminder.
    Skips creation if one already exists (duplicate-safe).
    """
    try:
        service   = get_calendar_service()
        now_ist   = _local_now()
        start_ist = now_ist.replace(hour=19, minute=55, second=0, microsecond=0)
        end_ist   = start_ist + timedelta(days=1)

        existing = service.events().list(
            calendarId              = "primary",
            timeMin                 = _ist_to_utc_z(start_ist),
            timeMax                 = _ist_to_utc_z(end_ist),
            privateExtendedProperty = f"source={SMARTSPEND_TAG}",
            q                       = "SmartSpend Reminder",
            singleEvents            = True,
        ).execute()

        if existing.get("items"):
            logger.info("Daily reminder already exists — skipping.")
            return False

        event = _build_event(
            summary     = "💸 SmartSpend Reminder",
            description = "Log your expenses today!",
            start       = now_ist.replace(hour=20, minute=0, second=0, microsecond=0),
            extra       = {"recurrence": ["RRULE:FREQ=DAILY"]},
        )
        return _insert_event(event)

    except Exception as exc:
        logger.error("create_recurring_daily_reminder failed: %s", exc)
        return False


def remove_today_reminder() -> bool:
    """
    Delete today's SmartSpend reminder instance regardless of what time
    the user adds an expense (searches the entire day, not just evening).
    Uses singleEvents=True so only today's instance is deleted,
    not the whole recurring series.
    """
    try:
        service  = get_calendar_service()
        now_ist  = _local_now()

        # ── FIX: search the ENTIRE day (midnight → midnight) ──────────────────
        # This way it works whether the user adds an expense at 9 AM or 9 PM
        day_start = now_ist.replace(hour=0,  minute=0,  second=0, microsecond=0)
        day_end   = now_ist.replace(hour=23, minute=59, second=59, microsecond=0)

        events = service.events().list(
            calendarId              = "primary",
            timeMin                 = _ist_to_utc_z(day_start),
            timeMax                 = _ist_to_utc_z(day_end),
            privateExtendedProperty = f"source={SMARTSPEND_TAG}",
            q                       = "SmartSpend Reminder",
            singleEvents            = True,
        ).execute()

        deleted = 0
        for event in events.get("items", []):
            try:
                service.events().delete(
                    calendarId = "primary",
                    eventId    = event["id"]
                ).execute()
                deleted += 1
                logger.info("Deleted today's reminder: %s", event.get("summary"))
            except Exception as exc:
                logger.warning("Could not delete event %s: %s", event.get("id"), exc)

        return deleted > 0

    except Exception as exc:
        logger.error("remove_today_reminder failed: %s", exc)
        return False


def create_streak_notification(streak_days: int) -> bool:
    """Celebrate a consecutive logging streak."""
    if streak_days < 2:
        return False
    event = _build_event(
        summary     = f"🔥 {streak_days}-Day Streak!",
        description = f"You've logged expenses for {streak_days} days in a row. Keep going 💪",
        start       = _local_now(),
    )
    return _insert_event(event)


def create_budget_warning(total: float, limit: float) -> bool:
    """Calendar alert for 80% budget usage."""
    pct   = int((total / limit) * 100)
    event = _build_event(
        summary     = "⚠️ Budget Almost Reached",
        description = f"You've used {pct}% of your budget — ₹{total:.2f} of ₹{limit:.2f}.",
        start       = _local_now(),
    )
    return _insert_event(event)


def create_budget_exceeded_alert(total: float, limit: float) -> bool:
    """Calendar alert when budget is exceeded."""
    overshoot = total - limit
    event     = _build_event(
        summary     = "🚨 Budget Exceeded!",
        description = f"You've exceeded your budget by ₹{overshoot:.2f} (₹{total:.2f} / ₹{limit:.2f}).",
        start       = _local_now(),
    )
    return _insert_event(event)


def create_month_end_reminder() -> bool:
    """Calendar reminder in the last 3 days of the month."""
    today    = _local_now()
    last_day = calendar.monthrange(today.year, today.month)[1]

    if today.day < last_day - 2:
        logger.info("create_month_end_reminder: too early, skipping.")
        return False

    event = _build_event(
        summary     = "📅 Month Ending Soon!",
        description = "Review your expenses and plan next month's budget.",
        start       = today.replace(hour=18, minute=0, second=0, microsecond=0),
    )
    return _insert_event(event)