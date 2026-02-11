from fastapi import APIRouter, HTTPException, Body, Path
from pydantic import BaseModel
from typing import List, Dict
from utils.file_handler import read_json, write_json
import os
from datetime import datetime

router = APIRouter()

PROFILES_PATH = os.path.join("database", "profiles.json")
EXPENSES_PATH = os.path.join("database", "expenses.json")

# -------------------------------
# Pydantic Models
# -------------------------------
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

# -------------------------------
# Helper: Sync fixed_expenses to expenses.json
# -------------------------------
def sync_fixed_expenses(username: str, fixed_expenses: List[Dict]):
    expenses = read_json(EXPENSES_PATH)

    # Remove old fixed expenses for this user
    expenses = [
        e for e in expenses
        if not (e.get("username") == username and e.get("category") == "fixed")
    ]

    now = datetime.now()
    month = now.strftime("%Y-%m")

    # Add new fixed expenses
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

# -------------------------------
# POST /profile/create
# -------------------------------
@router.post("/profile/create")
def create_profile(profile: dict = Body(...)):
    profiles = read_json(PROFILES_PATH)

    for p in profiles:
        if p.get("username") == profile["username"]:
            raise HTTPException(status_code=409, detail="User already exists")

    profiles.append(profile)
    write_json(PROFILES_PATH, profiles)

    sync_fixed_expenses(
        profile["username"],
        profile.get("fixed_expenses", [])
    )

    return {"message": "Profile created successfully"}

# -------------------------------
# GET /profile/{username}   ✅ REQUIRED FOR UPDATE PAGE
# -------------------------------
@router.get("/profile/{username}")
def get_profile(username: str = Path(...)):
    profiles = read_json(PROFILES_PATH)

    for p in profiles:
        if p.get("username") == username:
            return p

    raise HTTPException(status_code=404, detail="Profile not found")

# -------------------------------
# PUT /profile/update/{username}
# -------------------------------
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
            data["username"] = username   # KEEP original username
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
