from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from utils.file_handler import read_json, write_json
import os
import re

router = APIRouter()

# -------- PATH FIX (ONLY CHANGE) --------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # backend/
DB_PATH = os.path.join(BASE_DIR, "database", "users.json")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
if not os.path.exists(DB_PATH):
    write_json(DB_PATH, [])
# ---------------------------------------

# Input models
class RegisterData(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginData(BaseModel):
    identifier: str  # username or email
    password: str

class ResetPasswordData(BaseModel):
    identifier: str  # username or email
    new_password: str

# Password validation function
def is_valid_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[!@#$%^&*]", password):
        return False
    return True

# Register endpoint
@router.post("/register")
def register(data: RegisterData):
    users = read_json(DB_PATH)

    for user in users:
        if user.get("username") == data.username or user.get("email") == data.email:
            raise HTTPException(status_code=409, detail="User already exists")

    if not is_valid_password(data.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters, include 1 uppercase, 1 lowercase, and 1 special character (!@#$%^&*)"
        )

    users.append(data.dict())
    write_json(DB_PATH, users)

    print(f"User registered: {data.username}")
    return {"message": "Registration successful", "username": data.username}

# Login endpoint
@router.post("/login")
def login(data: LoginData):
    users = read_json(DB_PATH)

    for user in users:
        if data.identifier == user["username"] or data.identifier == user["email"]:
            if data.password == user["password"]:
                print(f"User logged in: {user['username']}")
                return {"message": "Login successful", "username": user["username"]}
            else:
                raise HTTPException(status_code=401, detail="Incorrect password")

    raise HTTPException(status_code=404, detail="User not found")

# Reset password endpoint
@router.post("/reset-password")
def reset_password(data: ResetPasswordData):
    users = read_json(DB_PATH)
    updated = False

    if not is_valid_password(data.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters, include 1 uppercase, 1 lowercase, and 1 special character (!@#$%^&*)"
        )

    for user in users:
        if data.identifier == user["username"] or data.identifier == user["email"]:
            user["password"] = data.new_password
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    write_json(DB_PATH, users)
    print(f"Password reset for: {data.identifier}")
    return {"message": "Password updated successfully"}
