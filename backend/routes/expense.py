from fastapi import APIRouter
from pydantic import BaseModel
from utils.file_handler import read_json, write_json
import os

router = APIRouter()

DB_PATH = os.path.join("database", "expenses.json")

class ExpenseData(BaseModel):
    username: str
    title: str
    amount: float
    category: str

@router.post("/add-expense")
def add_expense(data: ExpenseData):
    expenses = read_json(DB_PATH)
    expenses.append(data.dict())
    write_json(DB_PATH, expenses)
    print("Expense added")
    return {"message": "Expense added successfully"}
