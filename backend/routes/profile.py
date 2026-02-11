

from fastapi import APIRouter, HTTPException, Body

from pydantic import BaseModel
from typing import List, Dict
from utils.file_handler import read_json, write_json
import os

router = APIRouter()

PROFILES_PATH = os.path.join("database", "profiles.json")
EXPENSES_PATH = os.path.join("database", "expenses.json")

# Pydantic models
class FixedExpense(BaseModel):
    name: str
    amount: float
    category: str

class Profile(BaseModel):
    username: str
    first_name: str
    last_name: str
    working_status: str
    income: Dict[str, float]
    fixed_expenses: List[FixedExpense]

# Helper to sync fixed_expenses to expenses.json
def sync_fixed_expenses(username: str, fixed_expenses: List[Dict]):
    expenses = read_json(EXPENSES_PATH)

    # collect old variable expenses for this user
    user_variable = [e for e in expenses if e.get("username") == username and "title" in e]

    # remove old flat records of this user
    expenses = [e for e in expenses if e.get("username") != username or "title" not in e]

    # add grouped record
    expenses.append({
        "username": username,
        "fixed_expenses": fixed_expenses,
        "variable_expenses": user_variable
    })

    write_json(EXPENSES_PATH, expenses)


# POST /profile/create
@router.post("/profile/create")
def create_profile(profile: Profile = Body(...)):
    ...

    profiles = read_json(PROFILES_PATH)

    for p in profiles:
        if p.get("username") == profile.username:
            raise HTTPException(status_code=409, detail="User already exists")


    profiles.append(profile.dict())
    write_json(PROFILES_PATH, profiles)
    print(f"Profile created for {profile.username}")

    # Sync fixed expenses
    sync_fixed_expenses(profile.username, [fe.dict() for fe in profile.fixed_expenses])

    return {"message": "Profile created successfully"}

# PUT /profile/update/{username}
@router.put("/profile/update/{username}")
def update_profile(username: str, updated_profile: Profile = Body(...)):

    profiles = read_json(PROFILES_PATH)
    updated = False

    for i, p in enumerate(profiles):
     if p.get("username") == username:   # SAFE
        profiles[i] = updated_profile.dict()
        updated = True
        break


    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    write_json(PROFILES_PATH, profiles)
    print(f"Profile updated for {username}")

    # Sync fixed expenses
    sync_fixed_expenses(username, [fe.dict() for fe in updated_profile.fixed_expenses])

    return {"message": "Profile updated successfully"}
