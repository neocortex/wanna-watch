"""Verify password boundaries against the real application and SQLite store."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wanna_watch.app import create_app


def test_railway_requires_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed when a Railway deployment lacks credentials."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "test-environment")
    monkeypatch.delenv("WANNA_WATCH_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="WANNA_WATCH_PASSWORD"):
        create_app(tmp_path)


@pytest.mark.anyio
@pytest.mark.integration
async def test_protected_routes_and_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Protect pages, static assets, docs, reads, and writes while allowing readiness."""
    monkeypatch.setenv("WANNA_WATCH_PASSWORD", "secret")
    app = create_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
        assert (await client.get("/healthz")).json() == {"status": "ok"}
        for path in ["/", "/static/app.js", "/api/status", "/docs", "/openapi.json"]:
            response = await client.get(path)
            assert response.status_code == 401
            assert "www-authenticate" not in response.headers
        assert (await client.post("/api/refresh")).status_code == 401
        assert (await client.get("/api/status", auth=("watch", "wrong"))).status_code == 401
        await client.post("/login", data={"password": "secret"})
        response = await client.get("/api/status")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        for headers in [{"Origin": "https://evil.test"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}]:
            assert (
                await client.put("/api/preferences", json={"provider_ids": []}, headers=headers)
            ).status_code == 403
        assert (
            await client.put("/api/preferences", json={"provider_ids": []}, headers={"Origin": "https://test"})
        ).status_code == 200


def test_session_expiry_tampering_and_rotation() -> None:
    """Reject expired, forged, malformed and password-revoked sessions."""
    import time

    from wanna_watch.auth import SESSION_SECONDS, session_token, valid_session

    now = int(time.time())
    token = session_token("secret", now + SESSION_SECONDS)
    assert valid_session(token, "secret")
    assert not valid_session(token, "changed")
    assert not valid_session(token + "x", "secret")
    assert not valid_session(session_token("secret", now - 1), "secret")
    assert not valid_session(session_token("secret", now + SESSION_SECONDS + 60), "secret")
    for invalid in ["", "bad", "0", "1.é", f"{now + 60}.é"]:
        assert not valid_session(invalid, "secret")


@pytest.mark.anyio
@pytest.mark.integration
async def test_persistent_login_and_logout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue secure cookies, survive app restart and revoke browser access on logout."""
    from wanna_watch.auth import COOKIE, SESSION_SECONDS

    monkeypatch.setenv("WANNA_WATCH_PASSWORD", "secret")
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="https://test") as client:
        response = await client.get("/", headers={"Accept": "text/html"})
        assert response.headers["location"] == "/login"
        assert (await client.get("/login")).status_code == 200
        assert (await client.post("/login", data={"password": "wrong"})).headers["location"] == "/login?failed=1"
        assert COOKIE not in client.cookies
        assert (
            await client.post("/login", data={"password": "secret"}, headers={"Origin": "https://evil"})
        ).status_code == 403
        response = await client.post("/login", data={"password": "secret"})
        cookie = response.headers["set-cookie"]
        for attribute in ["HttpOnly", "Secure", "SameSite=lax", f"Max-Age={SESSION_SECONDS}"]:
            assert attribute in cookie
        cookies = client.cookies
    async with AsyncClient(
        transport=ASGITransport(create_app(tmp_path)), base_url="https://test", cookies=cookies
    ) as client:
        assert (await client.get("/api/status")).status_code == 200
        assert (await client.post("/logout")).status_code == 303
        assert (await client.get("/api/status")).status_code == 401
