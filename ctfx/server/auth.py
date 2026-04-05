"""Authentication — Bearer token middleware, one-time login tickets, cookie sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner


class TicketStore:
    """In-memory store for tracking redeemed one-time login tickets.

    Cleared on server restart (by design — per spec).
    """

    def __init__(self) -> None:
        self._redeemed: set[str] = set()

    def validate_and_redeem(
        self,
        ticket: str,
        root_token: str,
        token_version: int,
    ) -> bool:
        """Validate an HMAC-signed ticket and mark it as used.

        Returns True if valid, False otherwise.
        """
        try:
            parts = ticket.split(".")
            if len(parts) != 4:
                return False
            nonce, expires_str, tv_str, sig = parts
            expires = int(expires_str)
            tv = int(tv_str)
        except (ValueError, AttributeError):
            return False

        if tv != token_version:
            return False
        if time.time() > expires:
            return False

        payload = f"{nonce}.{expires_str}.{tv_str}"
        expected = hmac.new(
            root_token.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False
        if nonce in self._redeemed:
            return False

        self._redeemed.add(nonce)
        return True


def make_session_signer(root_token: str) -> TimestampSigner:
    return TimestampSigner(root_token, salt="ctfx-webui-session")


def make_session_cookie(root_token: str, token_version: int, session_ttl: int) -> str:
    """Sign a session value containing the token_version."""
    signer = make_session_signer(root_token)
    payload = f"v{token_version}"
    return signer.sign(payload).decode()


def verify_session_cookie(
    cookie_value: str,
    root_token: str,
    token_version: int,
    session_ttl: int,
) -> bool:
    """Return True if the cookie is valid, unexpired, and matches token_version."""
    signer = make_session_signer(root_token)
    try:
        payload = signer.unsign(cookie_value, max_age=session_ttl).decode()
    except (BadSignature, SignatureExpired):
        return False
    return payload == f"v{token_version}"


class AuthDeps:
    """Holds runtime auth state; injected into the FastAPI app state."""

    def __init__(self, root_token: str, token_version: int, auth_config: dict) -> None:
        self.root_token = root_token
        self.token_version = token_version
        self.auth_config = auth_config
        self.ticket_store = TicketStore()

    @property
    def cookie_name(self) -> str:
        return self.auth_config.get("webui_cookie_name", "ctfx_auth")

    @property
    def session_ttl(self) -> int:
        return self.auth_config.get("session_ttl_sec", 2592000)

    @property
    def ticket_ttl(self) -> int:
        return self.auth_config.get("one_time_login_ttl_sec", 60)


def _get_auth(request: Request) -> AuthDeps:
    return request.app.state.auth


def require_bearer(request: Request) -> None:
    """FastAPI dependency — validates Bearer token for API/MCP routes."""
    auth: AuthDeps = _get_auth(request)
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = header[len("Bearer "):]
    if not secrets.compare_digest(token, auth.root_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_cookie(request: Request) -> None:
    """FastAPI dependency — validates WebUI session cookie."""
    auth: AuthDeps = _get_auth(request)
    cookie_val = request.cookies.get(auth.cookie_name, "")
    if not cookie_val or not verify_session_cookie(
        cookie_val, auth.root_token, auth.token_version, auth.session_ttl
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )


def require_bearer_or_cookie(request: Request) -> None:
    """FastAPI dependency — accepts either a Bearer token or a valid session cookie."""
    auth: AuthDeps = _get_auth(request)
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[len("Bearer "):]
        if secrets.compare_digest(token, auth.root_token):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cookie_val = request.cookies.get(auth.cookie_name, "")
    if cookie_val and verify_session_cookie(
        cookie_val, auth.root_token, auth.token_version, auth.session_ttl
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid Authorization header",
        headers={"WWW-Authenticate": "Bearer"},
    )


BearerAuth = Annotated[None, Depends(require_bearer_or_cookie)]
CookieAuth = Annotated[None, Depends(require_cookie)]
