"""Simple password-based authentication with JWT tokens.

Provides a login endpoint and a FastAPI dependency for verifying tokens.
Auth is only enforced when ``settings.auth_password`` is configured.
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)

_ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_in_days: int


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    """Authenticate with the shared password and receive a JWT token."""
    if not settings.auth_password:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication is not configured",
        )

    if body.password != settings.auth_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    expire = datetime.now(timezone.utc) + timedelta(days=settings.auth_token_expire_days)
    payload = {"sub": "plant-tracker-user", "exp": expire}
    token = jwt.encode(payload, settings.auth_secret_key, algorithm=_ALGORITHM)

    return LoginResponse(token=token, expires_in_days=settings.auth_token_expire_days)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str | None:
    """FastAPI dependency that validates the JWT bearer token.

    When ``settings.auth_password`` is empty (auth disabled), all requests
    are allowed through without a token.

    Returns the token subject on success, or raises 401.
    """
    if not settings.auth_password:
        return None  # Auth disabled — allow all

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.auth_secret_key,
            algorithms=[_ALGORITHM],
        )
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
