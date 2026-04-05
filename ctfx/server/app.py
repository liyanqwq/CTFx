"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from ctfx.server.auth import (
    AuthDeps,
    make_session_cookie,
    verify_session_cookie,
)
from ctfx.server.api import router as api_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    root_token: str,
    token_version: int,
    auth_config: dict[str, Any],
    basedir: Path,
    active_competition: str | None,
    python_cmd: str,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    from ctfx.managers.config import CONFIG_FILE
    from ctfx.server.mcp_server import build_mcp_server

    active_competition_ref = {"value": active_competition}

    mcp_instance = build_mcp_server(
        basedir,
        active_competition_ref,
        python_cmd,
        config_path=CONFIG_FILE,
    )
    _mcp_app = mcp_instance.streamable_http_app()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        """Run MCP session manager for the lifetime of the FastAPI app."""
        async with mcp_instance.session_manager.run():
            yield

    app = FastAPI(title="CTFx", docs_url="/api/docs", redoc_url=None, lifespan=_lifespan)

    app.state.auth = AuthDeps(root_token, token_version, auth_config)
    app.state.basedir = basedir
    app.state.active_competition = active_competition
    app.state.active_competition_ref = active_competition_ref
    app.state.python_cmd = python_cmd
    app.state.config_path = CONFIG_FILE
    app.state.mcp_server = mcp_instance

    app.include_router(api_router)

    class _MCPGateway:
        """Auth-checking ASGI proxy for the MCP endpoint."""

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] == "http":
                request = Request(scope, receive)
                auth: AuthDeps = app.state.auth

                header = request.headers.get("Authorization", "")
                authed = False
                if header.startswith("Bearer "):
                    import secrets as _secrets
                    token = header[len("Bearer "):]
                    authed = _secrets.compare_digest(token, auth.root_token)
                else:
                    cookie_val = request.cookies.get(auth.cookie_name, "")
                    authed = bool(
                        cookie_val
                        and verify_session_cookie(
                            cookie_val, auth.root_token, auth.token_version, auth.session_ttl
                        )
                    )

                if not authed:
                    resp = JSONResponse(
                        {"detail": "Not authenticated"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    await resp(scope, receive, send)
                    return

            await _mcp_app(scope, receive, send)

    app.mount("/mcp", _MCPGateway())

    @app.get("/auth/webui/one-time-login")
    async def one_time_login(
        request: Request,
        ticket: str = "",
        next: str = "/",
    ) -> Response:
        auth: AuthDeps = request.app.state.auth

        parsed = urlparse(next)
        if parsed.scheme or parsed.netloc or not next.startswith("/"):
            next = "/"

        if not ticket or not auth.ticket_store.validate_and_redeem(
            ticket, auth.root_token, auth.token_version
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired login ticket",
            )

        cookie_value = make_session_cookie(
            auth.root_token, auth.token_version, auth.session_ttl
        )
        response = RedirectResponse(url=next, status_code=302)
        response.set_cookie(
            key=auth.cookie_name,
            value=cookie_value,
            max_age=auth.session_ttl,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(request: Request, full_path: str) -> Response:
            if full_path.startswith(("api/", "mcp/", "auth/")):
                raise HTTPException(status_code=404)
            auth: AuthDeps = request.app.state.auth
            cookie_val = request.cookies.get(auth.cookie_name, "")
            if not cookie_val or not verify_session_cookie(
                cookie_val, auth.root_token, auth.token_version, auth.session_ttl
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated. Use `ctfx webui` to log in.",
                )
            index = STATIC_DIR / "index.html"
            return HTMLResponse(index.read_text(encoding="utf-8"))
    else:
        @app.get("/", include_in_schema=False)
        async def no_webui(request: Request) -> Response:
            return HTMLResponse(
                "<h1>CTFx</h1>"
                "<p>WebUI not built. Run <code>npm run build</code> in <code>frontend/</code>.</p>"
                "<p>API docs: <a href='/api/docs'>/api/docs</a></p>",
                status_code=200,
            )

    return app
