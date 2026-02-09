from fastapi import APIRouter
from pydantic import BaseModel
from utils.file_handler import read_json
import os

router = APIRouter()

DB_PATH = os.path.join("database", "users.json")

class LoginData(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(data: LoginData):
    users = read_json(DB_PATH)
    for user in users:
        if user["username"] == data.username and user["password"] == data.password:
            print("User logged in successfully")
            return {"message": "Login successful"}
    print("Login failed")
    return {"error": "Invalid credentials"}
