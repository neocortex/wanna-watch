"""Protect the personal app with optional HTTP Basic authentication."""

import base64
import binascii
import secrets
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response


def valid_credentials(header: str, password: str) -> bool:
    """Check a Basic authorization header without exposing the configured password.

    Args:
        header: Incoming Authorization header.
        password: Shared password configured by the server owner.

    Returns:
        Whether the username and password match.
    """
    try:
        scheme, encoded = header.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return False
    return secrets.compare_digest(decoded, f"watch:{password}".encode())


def install_auth(app: FastAPI, password: str) -> None:
    """Require shared credentials for every route except the healthcheck.

    Args:
        app: Application whose routes and static files need protection.
        password: Shared password; empty disables protection for local use.
    """
    if not password:
        return

    @app.middleware("http")
    async def authenticate(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Authenticate requests and reject cross-site writes.

        Args:
            request: Incoming browser or API request.
            call_next: Next request handler.

        Returns:
            Authorized response or an authentication/access error.
        """
        if request.method == "GET" and request.url.path == "/healthz":
            return await call_next(request)
        if not valid_credentials(request.headers.get("authorization", ""), password):
            return JSONResponse(
                {"detail": "Sign in to Wanna Watch."},
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Wanna Watch", charset="UTF-8"'},
            )
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin is not None and urlsplit(origin).netloc != request.url.netloc
            ):
                return JSONResponse({"detail": "Cross-site writes are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
