from fastapi import APIRouter
from pydantic import BaseModel
from utils.file_handler import read_json, write_json
import os

router = APIRouter()

DB_PATH = os.path.join("database", "profiles.json")

class ProfileData(BaseModel):
    username: str
    email: str
    phone: str

@router.put("/edit-profile")
def edit_profile(data: ProfileData):
    profiles = read_json(DB_PATH)
    updated = False
    for profile in profiles:
        if profile["username"] == data.username:
            profile["email"] = data.email
            profile["phone"] = data.phone
            updated = True
            break
    if not updated:
        profiles.append(data.dict())
    write_json(DB_PATH, profiles)
    print("Profile updated")
    return {"message": "Profile updated"}
