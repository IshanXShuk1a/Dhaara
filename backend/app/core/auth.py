"""
Authentication / role-based authorization.

Roles: ADMIN, TRAFFIC_OPERATOR, VIEWER (see spec section 52/AUTHENTICATION).
Enforcement happens here, on the backend, via `require_role` - the frontend
hiding buttons is a UX nicety, never the actual authorization boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.database import get_db
from app.models.user import User

import bcrypt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ROLE_HIERARCHY = {"VIEWER": 0, "TRAFFIC_OPERATOR": 1, "ADMIN": 2}


def hash_password(password: str) -> str:
    # Truncate to 72 bytes if needed per bcrypt spec
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        pw_bytes = password.encode("utf-8")[:72]
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(username: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(minimum_role: str):
    """FastAPI dependency factory: `Depends(require_role("TRAFFIC_OPERATOR"))`
    rejects any user whose role is lower in ROLE_HIERARCHY than `minimum_role`."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if ROLE_HIERARCHY.get(user.role, -1) < ROLE_HIERARCHY.get(minimum_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires at least {minimum_role} role",
            )
        return user

    return _dependency
