from fastapi import Depends, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from app.services.auth import decode_access_token
from app.services.quotaGuard import set_current_user_id
import asyncpg

bearer_scheme = HTTPBearer()

class AuthUser:
    def __init__(self, user_id: str, username: str, role: str, is_privileged: bool = False):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.is_privileged = is_privileged

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    set_current_user_id(payload["sub"])
    return AuthUser(
        user_id=payload["sub"],
        username=payload["username"],
        role=payload["role"],
        is_privileged=payload.get("is_privileged", False),
    )
async def require_admin(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user

async def require_editor(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if current_user.role not in ("editor", "admin"):
        raise HTTPException(status_code=403, detail="Editor role required")
    return current_user



async def get_db(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool