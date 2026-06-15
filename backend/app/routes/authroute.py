from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.database import create_user, get_user_by_username
from app.services.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_db

router = APIRouter()

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "editor"

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/register", status_code=201)
async def register(body: RegisterRequest, db=Depends(get_db)):
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    hashed = hash_password(body.password)
    user = await create_user(db, body.username, hashed, body.role)
    return {"user_id": user["user_id"], "username": user["username"], "role": user["role"]}

@router.post("/auth/login")
async def login(body: LoginRequest, db=Depends(get_db)):
    user = await get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user["hashed_password"]):
        # Same error for both cases — don't reveal whether the username exists
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["user_id"], user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "username": user["username"],"role": user["role"],}