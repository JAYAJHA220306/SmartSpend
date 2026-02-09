from fastapi import FastAPI
from routes import login, expense, profile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow testing from browser or Postman
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(login.router)
app.include_router(expense.router)
app.include_router(profile.router)
