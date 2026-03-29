"""
SmartSpend - Email Notification Service (FIXED)
- monthly_job prev-month calculation corrected
- Once-per-month scheduler flags
- SMTP connection reuse
- Styled HTML templates
"""

import smtplib
import schedule
import time
import threading
import calendar
import logging
from contextlib import contextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from backend.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, BUDGET_LIMIT

logger          = logging.getLogger(__name__)
_scheduler_lock = threading.Lock()
_scheduler_flags: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

_BASE = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px}}
.card{{background:#fff;border-radius:12px;padding:28px 32px;max-width:520px;
       margin:auto;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
.header{{font-size:22px;font-weight:700;margin-bottom:16px;color:{accent}}}
.row{{display:flex;justify-content:space-between;padding:8px 0;
      border-bottom:1px solid #f0f0f0;font-size:15px;color:#444}}
.row:last-child{{border-bottom:none}}
.label{{color:#888}}.value{{font-weight:600;color:#222}}
.footer{{margin-top:24px;font-size:12px;color:#aaa;text-align:center}}
.badge{{display:inline-block;padding:4px 12px;border-radius:20px;
        background:{badge_bg};color:{badge_fg};font-size:13px;
        font-weight:600;margin-bottom:12px}}
</style></head><body><div class="card">
<div class="header">{header}</div>{body}
<div class="footer">SmartSpend &mdash; {date}</div>
</div></body></html>"""

def _render(header, body, accent="#2563eb", badge_bg="#eff6ff", badge_fg="#2563eb"):
    return _BASE.format(header=header, body=body, accent=accent,
                        badge_bg=badge_bg, badge_fg=badge_fg,
                        date=datetime.now().strftime("%d %b %Y"))

def _row(label, value):
    return f'<div class="row"><span class="label">{label}</span><span class="value">{value}</span></div>'

def _badge(text):
    return f'<div class="badge">{text}</div>'


# ══════════════════════════════════════════════════════════════════════════════
# SMTP
# ══════════════════════════════════════════════════════════════════════════════

@contextmanager
def _smtp_connection():
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    try:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        yield server
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_email(to_email: str, subject: str, html_body: str,
               _server: smtplib.SMTP | None = None) -> bool:
    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"SmartSpend 💰 <{GMAIL_ADDRESS}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        raw = msg.as_string()

        if _server:
            _server.sendmail(GMAIL_ADDRESS, to_email, raw)
        else:
            with _smtp_connection() as s:
                s.sendmail(GMAIL_ADDRESS, to_email, raw)

        logger.info("Email sent → %s | %s", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Email failed → %s | %s | %s", to_email, subject, exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def notify_expense_added(user_email, expense, _server=None):
    title    = expense.get("title", "Expense")
    amount   = expense.get("amount", 0)
    category = expense.get("category", "General")
    now      = datetime.now().strftime("%d %b %Y, %I:%M %p")
    body = (_badge("New Expense") + _row("Title", title) +
            _row("Amount", f"₹{amount:.2f}") + _row("Category", category) +
            _row("Time", now))
    return send_email(user_email, f"₹{amount:.2f} added — {title}",
                      _render("💸 Expense Added", body), _server)


def notify_budget_warning(user_email, total_spent, budget=BUDGET_LIMIT, _server=None):
    percent   = (total_spent / budget) * 100
    remaining = budget - total_spent
    body = (_badge(f"{percent:.1f}% used") + _row("Budget", f"₹{budget:.2f}") +
            _row("Spent", f"₹{total_spent:.2f}") + _row("Remaining", f"₹{remaining:.2f}"))
    return send_email(user_email, "⚠️ Budget Almost Full",
                      _render("⚠️ Budget Almost Full", body,
                              accent="#d97706", badge_bg="#fffbeb", badge_fg="#d97706"), _server)


def notify_budget_exceeded(user_email, total_spent, budget=BUDGET_LIMIT, _server=None):
    overage = total_spent - budget
    percent = (total_spent / budget) * 100
    body = (_badge(f"{percent:.1f}% used") + _row("Budget", f"₹{budget:.2f}") +
            _row("Spent", f"₹{total_spent:.2f}") + _row("Over by", f"₹{overage:.2f}"))
    return send_email(user_email, "🚨 Budget Exceeded!",
                      _render("🚨 Budget Exceeded!", body,
                              accent="#dc2626", badge_bg="#fef2f2", badge_fg="#dc2626"), _server)


def notify_month_end(user_email, total_spent, budget=BUDGET_LIMIT, _server=None):
    remaining = budget - total_spent
    status    = "Under budget 🎉" if remaining >= 0 else f"Over by ₹{abs(remaining):.2f} 😬"
    body = (_badge("Month Ending Soon") + _row("Budget", f"₹{budget:.2f}") +
            _row("Spent", f"₹{total_spent:.2f}") + _row("Remaining", f"₹{remaining:.2f}") +
            _row("Status", status))
    return send_email(user_email, "📅 Month Ending Soon",
                      _render("📅 Month Ending Soon", body,
                              accent="#7c3aed", badge_bg="#f5f3ff", badge_fg="#7c3aed"), _server)


def send_daily_summary(user_email, expenses, _server=None):
    today = date.today().strftime("%d %b %Y")
    total = sum(e.get("amount", 0) for e in expenses)
    count = len(expenses)

    if not expenses:
        body = (_badge("No Expenses Today") +
                "<p style='color:#555;margin-top:12px'>You haven't logged any expenses today 👀</p>")
        return send_email(user_email, f"📊 Daily Summary — {today} (No Entries)",
                          _render(f"📊 Daily Summary — {today}", body,
                                  accent="#64748b", badge_bg="#f8fafc", badge_fg="#64748b"), _server)

    rows = "".join(_row(e.get("title", "—"), f"₹{e.get('amount', 0):.2f}") for e in expenses)
    body = _badge(f"{count} expense{'s' if count != 1 else ''} today") + rows + _row("Total", f"₹{total:.2f}")
    return send_email(user_email, f"📊 Daily Summary — ₹{total:.2f} | {today}",
                      _render(f"📊 Daily Summary — {today}", body), _server)


def send_weekly_report(user_email, expenses, _server=None):
    total  = sum(e.get("amount", 0) for e in expenses)
    count  = len(expenses)
    by_cat: dict[str, float] = {}
    for e in expenses:
        cat = e.get("category", "Other")
        by_cat[cat] = by_cat.get(cat, 0) + e.get("amount", 0)

    cat_rows = "".join(_row(c, f"₹{a:.2f}") for c, a in sorted(by_cat.items(), key=lambda x: -x[1]))
    body = _badge(f"{count} expense{'s' if count != 1 else ''} this week") + cat_rows + _row("Total", f"₹{total:.2f}")
    return send_email(user_email, f"📊 Weekly Report — ₹{total:.2f}",
                      _render("📊 Weekly Report", body), _server)


def send_monthly_report(user_email, expenses, income, budget=BUDGET_LIMIT, _server=None):
    month  = datetime.now().strftime("%B %Y")
    total  = sum(e.get("amount", 0) for e in expenses)
    saved  = income - total
    by_cat: dict[str, float] = {}
    for e in expenses:
        cat = e.get("category", "Other")
        by_cat[cat] = by_cat.get(cat, 0) + e.get("amount", 0)

    cat_rows = "".join(_row(c, f"₹{a:.2f}") for c, a in sorted(by_cat.items(), key=lambda x: -x[1]))
    status   = "Under budget 🎉" if total <= budget else f"Over by ₹{total - budget:.2f} 🚨"
    body = (_badge(month) + _row("Income", f"₹{income:.2f}") +
            _row("Budget", f"₹{budget:.2f}") + _row("Spent", f"₹{total:.2f}") +
            _row("Saved", f"₹{saved:.2f}") + _row("Status", status) +
            "<div style='margin-top:16px;font-weight:600;color:#555'>By Category</div>" + cat_rows)
    return send_email(user_email, f"📅 Monthly Report — {month}",
                      _render(f"📅 Monthly Report — {month}", body,
                              accent="#059669", badge_bg="#ecfdf5", badge_fg="#059669"), _server)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _flag_key(username, flag, period):
    return f"{username}:{flag}:{period}"

def _prev_month_str(today: datetime) -> str:
    """Return YYYY-MM string for the month before today."""
    first_this_month = today.replace(day=1)
    last_prev        = first_this_month - timedelta(days=1)
    return last_prev.strftime("%Y-%m")


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════

def start_scheduler(get_users_fn, get_user_expenses_fn):
    """
    get_users_fn()                      → list[{username, email, income}]
    get_user_expenses_fn(username, month) → list[expense dicts]
    """

    def daily_job():
        with _scheduler_lock:
            logger.info("[Scheduler] Daily job running...")
            today     = date.today().strftime("%Y-%m-%d")
            cur_month = datetime.now().strftime("%Y-%m")
            now_dt    = datetime.now()
            last_day  = calendar.monthrange(now_dt.year, now_dt.month)[1]

            try:
                users = get_users_fn()
                with _smtp_connection() as server:
                    for user in users:
                        email    = user.get("email")
                        username = user.get("username")
                        if not email or not username:
                            continue

                        all_month  = get_user_expenses_fn(username, cur_month)
                        today_exp  = [e for e in all_month if e.get("created_at", "").startswith(today)]
                        monthly_total = sum(e.get("amount", 0) for e in all_month)

                        # Daily summary (handles empty too)
                        send_daily_summary(email, today_exp, server)

                        # 80% warning — once per month
                        warn_key = _flag_key(username, "sched_warning", cur_month)
                        if (BUDGET_LIMIT * 0.8 <= monthly_total < BUDGET_LIMIT
                                and not _scheduler_flags.get(warn_key)):
                            notify_budget_warning(email, monthly_total, _server=server)
                            _scheduler_flags[warn_key] = True

                        # Month-end — once per month, last 3 days
                        me_key = _flag_key(username, "sched_month_end", cur_month)
                        if now_dt.day >= last_day - 2 and not _scheduler_flags.get(me_key):
                            notify_month_end(email, monthly_total, _server=server)
                            _scheduler_flags[me_key] = True

            except Exception as exc:
                logger.error("[Scheduler] daily_job error: %s", exc)

    def weekly_job():
        with _scheduler_lock:
            logger.info("[Scheduler] Weekly job running...")
            cur_month = datetime.now().strftime("%Y-%m")
            try:
                users = get_users_fn()
                with _smtp_connection() as server:
                    for user in users:
                        email    = user.get("email")
                        username = user.get("username")
                        if not email or not username:
                            continue
                        send_weekly_report(email, get_user_expenses_fn(username, cur_month), server)
            except Exception as exc:
                logger.error("[Scheduler] weekly_job error: %s", exc)

    def monthly_job():
        """
        Runs daily at 09:00 but fires only on days 1–3 of the month.
        Retries on day 2/3 if server was down on day 1.
        Reports on the PREVIOUS month's expenses.
        """
        today = datetime.now()
        if today.day > 3:
            return

        send_key = f"monthly_report:{today.strftime('%Y-%m')}"
        if _scheduler_flags.get(send_key):
            return

        with _scheduler_lock:
            logger.info("[Scheduler] Monthly job running...")
            prev_month = _prev_month_str(today)   # ← FIXED: correct prev-month calc
            try:
                users = get_users_fn()
                with _smtp_connection() as server:
                    for user in users:
                        email    = user.get("email")
                        username = user.get("username")
                        income   = user.get("income", 0)
                        if not email or not username:
                            continue
                        expenses = get_user_expenses_fn(username, prev_month)
                        send_monthly_report(email, expenses, income, _server=server)
                _scheduler_flags[send_key] = True
            except Exception as exc:
                logger.error("[Scheduler] monthly_job error: %s", exc)

    schedule.every().day.at("20:00").do(daily_job)
    schedule.every().monday.at("09:00").do(weekly_job)
    schedule.every().day.at("09:00").do(monthly_job)

    def _run():
        logger.info("[Scheduler] Background thread started.")
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=_run, daemon=True, name="SmartSpend-Scheduler").start()