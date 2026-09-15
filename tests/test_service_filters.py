"""Verify independent service selection using real routing and SQLite boundary inputs."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from wanna_watch.app import Preferences, create_app


def test_service_selection_defaults_and_bounds() -> None:
    """Preserve legacy all-services preferences and distinguish an explicit empty selection."""
    assert Preferences(provider_ids=[8]).service_ids is None
    assert Preferences(provider_ids=[8], service_ids=[]).service_ids == []
    with pytest.raises(ValidationError):
        Preferences(provider_ids=[8], service_ids=list(range(31)))


@pytest.mark.integration
@pytest.mark.anyio
async def test_service_subset_ranking_coverage_and_restart(tmp_path: Path, films: list[dict]) -> None:
    """Filter before pagination without changing ownership, history, or snapshot coverage."""
    app = create_app(tmp_path)
    store = app.state.store
    store.set("providers", [{"provider_id": 8}, {"provider_id": 9}])
    films[0]["providers"] = [{"provider_id": 9, "provider_name": "Amazon Prime Video"}]
    store.publish(films, {"provider_ids": [8, 9], "started_at": datetime.now(UTC).isoformat()})
    prefs = {"provider_ids": [8, 9], "service_ids": [8], "min_votes": 0}
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.put("/api/preferences", json=prefs)).status_code == 200
        result = (await client.get("/api/movies?limit=1&offset=1")).json()
        assert result["total"] == 3
        assert result["movies"][0]["id"] == 155
        status = (await client.get("/api/status")).json()
        assert status["preferences"]["provider_ids"] == [8, 9]
        assert status["snapshot"]["provider_ids"] == [8, 9]
        assert status["needs_refresh"] is False
        assert (await client.put("/api/preferences", json={**prefs, "service_ids": [10]})).status_code == 422
        assert (await client.put("/api/preferences", json={**prefs, "provider_ids": [9]})).status_code == 422
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as client:
        assert (await client.get("/api/status")).json()["preferences"]["service_ids"] == [8]
        await client.put("/api/preferences", json={**prefs, "service_ids": []})
        assert (await client.get("/api/movies")).json() == {"movies": [], "total": 0}
        await client.put("/api/preferences", json={**prefs, "service_ids": None})
        assert (await client.get("/api/movies")).json()["total"] == 4
