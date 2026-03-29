from fastapi import APIRouter, HTTPException, Body, Path
from pydantic import BaseModel
from typing import List, Dict
from backend.utils.file_handler import read_json, write_json
import os
from datetime import datetime

router = APIRouter()

# -------- PATH FIX --------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # backend/
PROFILES_PATH = os.path.join(BASE_DIR, "database", "profiles.json")
EXPENSES_PATH = os.path.join(BASE_DIR, "database", "expenses.json")

os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)
if not os.path.exists(PROFILES_PATH):
    write_json(PROFILES_PATH, [])
if not os.path.exists(EXPENSES_PATH):
    write_json(EXPENSES_PATH, [])
# --------------------------

class FixedExpense(BaseModel):
    name: str
    amount: float
    category: str

class Profile(BaseModel):
    first_name: str
    last_name: str
    working_status: str
    income: Dict[str, float]
    fixed_expenses: List[FixedExpense]


def sync_fixed_expenses(username: str, fixed_expenses: List[Dict]):
    expenses = read_json(EXPENSES_PATH)

    expenses = [
        e for e in expenses
        if not (e.get("username") == username and e.get("category") == "fixed")
    ]

    now = datetime.now()
    month = now.strftime("%Y-%m")

    for fx in fixed_expenses:
        expenses.append({
            "username": username,
            "title": fx["name"],
            "amount": fx["amount"],
            "category": "fixed",
            "created_at": now.isoformat(),
            "month": month
        })

    write_json(EXPENSES_PATH, expenses)
    print(f"Fixed expenses synced for {username}")


@router.post("/profile/create")
def create_profile(profile: dict = Body(...)):
    profiles = read_json(PROFILES_PATH)

    for p in profiles:
        if p.get("username") == profile["username"]:
            raise HTTPException(status_code=409, detail="User already exists")

    profiles.append(profile)
    write_json(PROFILES_PATH, profiles)

    sync_fixed_expenses(profile["username"], profile.get("fixed_expenses", []))

    return {"message": "Profile created successfully"}


@router.get("/profile/{username}")
def get_profile(username: str = Path(...)):
    profiles = read_json(PROFILES_PATH)

    for p in profiles:
        if p.get("username") == username:
            return p

    raise HTTPException(status_code=404, detail="Profile not found")


@router.put("/profile/update/{username}")
def update_profile(
    username: str = Path(...),
    updated_profile: Profile = Body(...)
):
    profiles = read_json(PROFILES_PATH)
    updated = False

    for i, p in enumerate(profiles):
        if p.get("username") == username:
            data = updated_profile.dict()
            data["username"] = username
            profiles[i] = data
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")

    write_json(PROFILES_PATH, profiles)

    sync_fixed_expenses(
        username,
        [fe.dict() for fe in updated_profile.fixed_expenses]
    )

    return {"message": "Profile updated successfully"}

