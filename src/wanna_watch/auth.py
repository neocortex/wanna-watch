"""Protect the personal app with persistent signed sessions."""

import hashlib
import hmac
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response

SESSION_SECONDS = 30 * 24 * 60 * 60
COOKIE = "wanna_watch_session"
STATIC = Path(__file__).parent / "static"


def session_token(password: str, expires: int) -> str:
    """Sign a session expiry using a key tied to the current password.

    Args:
        password: Server's shared password.
        expires: Unix timestamp when the session expires.

    Returns:
        Signed cookie value without credentials.
    """
    payload = str(expires)
    signature = hmac.new(password.encode(), f"wanna-watch-session:{payload}".encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def valid_session(token: str, password: str) -> bool:
    """Validate signature and server-side expiration of a session.

    Args:
        token: Incoming cookie value.
        password: Current server password, allowing rotation to revoke sessions.

    Returns:
        Whether the signed session is still valid.
    """
    try:
        expires = int(token.split(".", 1)[0])
    except ValueError:
        return False
    remaining = expires - time.time()
    return 0 < remaining <= SESSION_SECONDS and secrets.compare_digest(
        token.encode(), session_token(password, expires).encode()
    )


def install_auth(app: FastAPI, password: str) -> None:
    """Protect the application and provide a persistent password login.

    Args:
        app: Application whose routes and static files need protection.
        password: Shared password; empty disables protection for local use.
    """

    @app.middleware("http")
    async def authenticate(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Route login requests and enforce authentication and same-origin writes.

        Args:
            request: Incoming browser or API request.
            call_next: Next request handler.

        Returns:
            Authorized response or a login/access response.
        """
        path = request.url.path
        if not password:
            if path in {"/login", "/logout"}:
                return RedirectResponse("/", status_code=303)
            return await call_next(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin is not None and urlsplit(origin).netloc != request.url.netloc
            ):
                return JSONResponse({"detail": "Cross-site writes are not allowed."}, status_code=403)
        if path == "/login" and request.method == "GET":
            return FileResponse(STATIC / "login.html", headers={"Cache-Control": "no-store"})
        if path == "/login" and request.method == "POST":
            body = await request.body()
            if len(body) > 8192:
                return Response(status_code=413)
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            supplied = fields.get("password", [""])[0]
            if not secrets.compare_digest(supplied.encode(), password.encode()):
                return RedirectResponse("/login?failed=1", status_code=303, headers={"Cache-Control": "no-store"})
            response = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
            response.set_cookie(
                COOKIE,
                session_token(password, int(time.time()) + SESSION_SECONDS),
                max_age=SESSION_SECONDS,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
            )
            return response
        if path == "/logout" and request.method == "POST":
            response = RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
            response.delete_cookie(COOKIE)
            return response
        public_asset = path in {"/static/style.css", "/static/login.css", "/static/login.js"} or (
            path.startswith("/static/fonts/") and ".." not in path
        )
        if request.method == "GET" and (path == "/healthz" or public_asset):
            return await call_next(request)
        authorized = valid_session(request.cookies.get(COOKIE, ""), password)
        if not authorized:
            if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
                return RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
            return JSONResponse({"detail": "Sign in to Wanna Watch."}, status_code=401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
