from fastapi import APIRouter
from pydantic import BaseModel
from utils.file_handler import read_json, write_json
from typing import Optional
from datetime import datetime
import os

router = APIRouter()
DB_PATH = os.path.join("database", "expenses.json")

# Pydantic model with auto-generated fields
class ExpenseData(BaseModel):
    username: str
    title: str
    amount: float
    category: str  # e.g., "food", "travel", "fixed"
    created_at: Optional[str] = None  # Auto-filled
    month: Optional[str] = None       # Auto-filled

# Helper function to inject fixed expenses for a new month
def inject_fixed_expenses(username: str, current_month: str, expenses: list):
    # Check if fixed expenses already exist for this user and month
    already_added = any(
        e["username"] == username and e["month"] == current_month and e["category"] == "fixed"
        for e in expenses
    )
    if already_added:
        return  # Skip if already added

    # Find previous fixed expenses
    previous_fixed = [
        e for e in expenses
        if e["username"] == username and e["category"] == "fixed"
    ]
    if not previous_fixed:
        return  # No fixed expenses to copy

    # Get the latest month from previous fixed expenses
    latest_month = sorted({e["month"] for e in previous_fixed})[-1]
    fixed_to_copy = [
        e for e in previous_fixed if e["month"] == latest_month
    ]

    # Duplicate fixed expenses for the new month
    for item in fixed_to_copy:
        new_item = item.copy()
        new_item["created_at"] = datetime.now().isoformat()
        new_item["month"] = current_month
        expenses.append(new_item)
    print(f"Fixed expenses duplicated for {username} in {current_month}")

# POST /add-expense endpoint
@router.post("/add-expense")
def add_expense(data: ExpenseData):
    expenses = read_json(DB_PATH)

    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    data.created_at = now.isoformat()
    data.month = current_month

    # Inject fixed expenses if it's the first expense of the month
    inject_fixed_expenses(data.username, current_month, expenses)

    # Add the new expense
    expenses.append(data.dict())
    write_json(DB_PATH, expenses)
    print(f"Expense added for {data.username} in {current_month}")
    return {"message": "Expense added successfully"}

# GET /expenses/{username}/{month} endpoint
@router.get("/expenses/{username}/{month}")
def get_monthly_expenses(username: str, month: str):
    expenses = read_json(DB_PATH)
    filtered = [
        e for e in expenses
        if e["username"] == username and e["month"] == month
    ]
    print(f"Returned {len(filtered)} expenses for {username} in {month}")
    return {"expenses": filtered}

