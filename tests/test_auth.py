"""Verify password boundaries against the real application and SQLite store."""

import base64
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wanna_watch.app import create_app
from wanna_watch.auth import valid_credentials


@pytest.mark.parametrize("header", ["", "Bearer abc", "Basic !!!", "Basic /w==", "Basic d2F0Y2g6d3Jvbmc="])
def test_invalid_credentials(header: str) -> None:
    """Reject missing, malformed, and incorrect credentials."""
    assert not valid_credentials(header, "secret")


def test_unicode_password() -> None:
    """Accept UTF-8 passwords with colons using the fixed watch username."""
    header = "Basic " + base64.b64encode("watch:sëcret:phrase".encode()).decode()
    assert valid_credentials(header, "sëcret:phrase")


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
            assert response.headers["www-authenticate"].startswith("Basic ")
        assert (await client.post("/api/refresh")).status_code == 401
        assert (await client.get("/api/status", auth=("watch", "wrong"))).status_code == 401
        client.auth = ("watch", "secret")
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
