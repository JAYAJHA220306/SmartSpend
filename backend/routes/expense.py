from fastapi import APIRouter
from pydantic import BaseModel
from utils.file_handler import read_json, write_json
from typing import Optional
from datetime import datetime
import os

router = APIRouter()

# -------- PATH FIX --------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # backend/
DB_PATH = os.path.join(BASE_DIR, "database", "expenses.json")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
if not os.path.exists(DB_PATH):
    write_json(DB_PATH, [])
# --------------------------

class ExpenseData(BaseModel):
    username: str
    title: str
    amount: float
    category: str
    created_at: Optional[str] = None
    month: Optional[str] = None


@router.post("/add-expense")
def add_expense(data: ExpenseData):
    expenses = read_json(DB_PATH)

    now = datetime.now()
    data.created_at = now.isoformat()
    data.month = now.strftime("%Y-%m")

    expenses.append(data.dict())
    write_json(DB_PATH, expenses)

    print(f"Expense added for {data.username}")
    return {"message": "Expense added successfully"}


@router.get("/expense/{username}")
def get_expenses(username: str):
    expenses = read_json(DB_PATH)
    user_expenses = [e for e in expenses if e.get("username") == username]
    return {"expenses": user_expenses}

