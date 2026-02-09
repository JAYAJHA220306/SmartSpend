from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from utils.file_handler import read_json, write_json
import os

router = APIRouter()
DB_PATH = os.path.join("database", "profiles.json")


class ProfileData(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    working_status: str = Field(..., pattern="^(student|working_professional)$")
    income: Dict[str, float]
    fixed_expenses: Optional[Dict[str, float]] = {}


def validate_income(data: ProfileData):
    if data.working_status == "student":
        if "allowance" not in data.income or "monthly_salary" in data.income:
            raise HTTPException(
                status_code=400,
                detail="Students must have only 'allowance' in income."
            )

    elif data.working_status == "working_professional":
        if "monthly_salary" not in data.income or "allowance" in data.income:
            raise HTTPException(
                status_code=400,
                detail="Working professionals must have only 'monthly_salary' in income."
            )


# ---------------- CREATE ----------------
@router.post("/profile")
def create_profile(data: ProfileData):
    profiles: List[dict] = read_json(DB_PATH)
    validate_income(data)

    for profile in profiles:
        if profile.get("user_id") == data.user_id:
            raise HTTPException(status_code=400, detail="Profile already exists")

    profiles.append(data.dict())
    write_json(DB_PATH, profiles)

    return {"message": "Profile created", "profile": data.dict()}


# ---------------- UPDATE ----------------
@router.put("/profile/{user_id}")
def update_profile(user_id: str, data: ProfileData):
    profiles: List[dict] = read_json(DB_PATH)
    validate_income(data)

    for profile in profiles:
        if profile.get("user_id") == user_id:
            profile["first_name"] = data.first_name
            profile["last_name"] = data.last_name
            profile["working_status"] = data.working_status
            profile["income"] = data.income
            profile["fixed_expenses"] = data.fixed_expenses

            write_json(DB_PATH, profiles)
            return {"message": "Profile updated", "profile": profile}

    raise HTTPException(status_code=404, detail="Profile not found")
