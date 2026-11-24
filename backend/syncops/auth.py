import hashlib
import hmac
import os
import secrets
import time
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DatabaseSession

from .database import Session
from .models import AuthSession, Integration, User

SESSION_SECONDS = 8 * 60 * 60
BEARER = HTTPBearer(auto_error=False)
DUMMY_HASH = f"{'0' * 32}:{'0' * 64}"
LOGIN_SLOTS = BoundedSemaphore(2)


def password_key(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**17,
        r=8,
        p=1,
        maxmem=192 * 1024 * 1024,
        dklen=32,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"{salt.hex()}:{password_key(password, salt).hex()}"


def check_password(password: str, encoded: str) -> bool:
    salt, expected = encoded.split(":")
    return hmac.compare_digest(password_key(password, bytes.fromhex(salt)), bytes.fromhex(expected))


def token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bootstrap() -> None:
    with Session.begin() as db:
        for role in ("admin", "operator", "viewer"):
            if db.get(User, role) is not None:
                continue
            password = os.getenv(f"SYNCOPS_{role.upper()}_PASSWORD")
            if not password and role == "admin":
                raise RuntimeError("Set SYNCOPS_ADMIN_PASSWORD for initial account setup")
            if not password:
                continue
            if not 12 <= len(password) <= 256:
                raise RuntimeError("Bootstrap passwords must contain 12 to 256 characters")
            db.add(User(username=role, role=role, password_hash=hash_password(password)))
        if db.scalar(select(Integration.id).limit(1)) is None:
            for source, destination, purpose in (
                ("crm", "erp", "Sync company and contact data into the mock ERP."),
                ("erp", "tms", "Send synthetic orders to the mock transport system."),
                ("tms", "crm", "Sync shipment updates to the mock CRM."),
            ):
                db.add(
                    Integration(
                        name=f"Mock {source.upper()} → Mock {destination.upper()}",
                        description=purpose,
                        source=source,
                        destination=destination,
                        timeout_seconds=2,
                        max_attempts=4,
                        retry_base_seconds=1,
                    )
                )


def get_db():
    with Session() as db:
        yield db


Db = Annotated[DatabaseSession, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)]


def current_session(db: Db, credentials: Credentials) -> tuple[User, AuthSession]:
    if credentials is None or len(credentials.credentials) > 256:
        raise HTTPException(401, "Session required", headers={"WWW-Authenticate": "Bearer"})
    session = db.get(AuthSession, token_key(credentials.credentials))
    if session is None or session.expires_at <= time.time():
        raise HTTPException(401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, session.username)
    if user is None:
        raise HTTPException(401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"})
    return user, session


def current_user(auth: Annotated[tuple[User, AuthSession], Depends(current_session)]) -> User:
    return auth[0]


Actor = Annotated[User, Depends(current_user)]


def require_roles(*roles: str):
    def authorize(user: Actor) -> User:
        if user.role not in roles:
            raise HTTPException(403, "This action requires an elevated role")
        return user

    return authorize


Admin = Annotated[User, Depends(require_roles("admin"))]
Operator = Annotated[User, Depends(require_roles("admin", "operator"))]


def issue_session(db: DatabaseSession, username: str, password: str) -> tuple[str, User]:
    if not LOGIN_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Sign-in is busy, retry shortly", headers={"Retry-After": "1"})
    try:
        user = db.get(User, username)
        valid = check_password(password, user.password_hash if user else DUMMY_HASH)
    finally:
        LOGIN_SLOTS.release()
    if not valid or user is None:
        raise HTTPException(401, "Invalid username or password", headers={"WWW-Authenticate": "Bearer"})
    now = time.time()
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=token_key(token), username=username, expires_at=now + SESSION_SECONDS))
    return token, user
