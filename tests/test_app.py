"""Exercise real HTTP routing and SQLite persistence without mocking upstream services."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wanna_watch.app import create_app

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_empty_app_and_invalid_requests(tmp_path: Path) -> None:
    """Expose an honest empty state and reject unsupported subscriptions and actions."""
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as client:
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/api/movies")).json() == {"movies": [], "total": 0}
        assert (await client.get("/api/status")).json()["snapshot"] is None
        assert (await client.post("/api/refresh")).status_code == 422
        assert (await client.put("/api/preferences", json={"provider_ids": [99999999]})).status_code == 422
        assert (await client.put("/api/preferences", json={"provider_ids": [], "min_votes": -1})).status_code == 422
        assert (await client.get("/api/movies?offset=-1")).status_code == 422
        assert (await client.get("/api/movies?limit=101")).status_code == 422
        assert (await client.get("/api/movies?view=invalid")).status_code == 422
        assert (await client.put("/api/movies/1/state", json={"state": "watched"})).status_code == 404
        assert (await client.put("/api/movies/1/state", json={"state": "invalid"})).status_code == 422


async def test_rank_before_pagination_and_persist_actions(tmp_path: Path, films: list[dict]) -> None:
    """Ensure the API slices after global sorting and history is retained on restart."""
    app = create_app(tmp_path)
    store = app.state.store
    store.set("providers", [{"provider_id": 8, "provider_name": "Netflix"}])
    store.publish(films, {"provider_ids": [8], "started_at": datetime.now(UTC).isoformat()})
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.put("/api/preferences", json={"provider_ids": [8], "min_votes": 0})).status_code == 200
        page1 = (await client.get("/api/movies?limit=2")).json()
        page2 = (await client.get("/api/movies?limit=2&offset=2")).json()
        assert [m["id"] for m in page1["movies"]] == [278, 238]
        assert [m["id"] for m in page2["movies"]] == [155, 13]
        assert page1["total"] == page2["total"] == 4
        assert (await client.put("/api/movies/278/state", json={"state": "watched"})).status_code == 200
        assert (await client.get("/api/movies")).json()["movies"][0]["id"] == 238
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as reopened:
        assert (await reopened.get("/api/movies?view=watched")).json()["movies"][0]["id"] == 278
        assert (await reopened.put("/api/movies/278/state", json={"state": "unseen"})).status_code == 200
        assert (await reopened.get("/api/movies")).json()["movies"][0]["id"] == 278


async def test_stale_and_uncovered_services_require_refresh(tmp_path: Path, films: list[dict]) -> None:
    """Distinguish a recent complete selection from stale or uncovered snapshots."""
    app = create_app(tmp_path)
    store = app.state.store
    store.set("preferences", {"provider_ids": [8, 9], "min_votes": 5000})
    store.publish(films, {"provider_ids": [8], "started_at": datetime.now(UTC).isoformat()})
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/api/status")).json()["needs_refresh"] is True
        store.set("preferences", {"provider_ids": [8], "min_votes": 5000})
        assert (await client.get("/api/status")).json()["needs_refresh"] is False
        store.publish(films, {"provider_ids": [8], "started_at": "2020-01-01T00:00:00+00:00"})
        assert (await client.get("/api/status")).json()["stale"] is True


async def test_saved_metadata_filters_apply_before_pagination(tmp_path: Path, films: list[dict]) -> None:
    """Persist combined filters, enforce validation, and slice only matching films."""
    app = create_app(tmp_path)
    store = app.state.store
    store.set("providers", [{"provider_id": 8}])
    store.set("genres", [{"id": 99, "name": "Documentary"}])
    for film in films:
        film.update(year="1991", original_language="en", genres=[], is_standup=False)
    films[0]["year"] = "1990"
    films[2]["genres"] = [{"id": 99, "name": "Documentary"}]
    store.publish(films, {"provider_ids": [8], "started_at": datetime.now(UTC).isoformat()})
    prefs = {
        "provider_ids": [8],
        "media_type": "movie",
        "service_ids": None,
        "min_votes": 0,
        "excluded_genres": [99],
        "exclude_standup": True,
        "language": "en",
        "after_year": 1990,
        "imdb_rating": None,
    }
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.put("/api/preferences", json=prefs)).json() == prefs
        first = (await client.get("/api/movies?limit=1")).json()
        second = (await client.get("/api/movies?limit=1&offset=1")).json()
        assert first["total"] == second["total"] == 2
        assert [first["movies"][0]["id"], second["movies"][0]["id"]] == [155, 13]
        for invalid in [
            {"language": "invalid"},
            {"after_year": -1},
            {"after_year": 1990.5},
            {"excluded_genres": [999]},
        ]:
            assert (await client.put("/api/preferences", json={**prefs, **invalid})).status_code == 422
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as client:
        assert (await client.get("/api/status")).json()["preferences"] == prefs
        assert (await client.get("/api/movies")).json()["total"] == 2


async def test_maximum_rating_validation_pagination_and_restart(tmp_path: Path, films: list[dict]) -> None:
    """Persist a rating ceiling and paginate through lower scores with validated bounds."""
    app = create_app(tmp_path)
    app.state.store.set("providers", [{"provider_id": 8}])
    app.state.store.publish(films, {"provider_ids": [8], "started_at": datetime.now(UTC).isoformat()})
    prefs = {"provider_ids": [8], "min_votes": 0, "imdb_rating": 9.2}
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.put("/api/preferences", json=prefs)).status_code == 200
        result = (await client.get("/api/movies?limit=1")).json()
        assert result["total"] == 3
        assert result["movies"][0]["id"] == 238
        lower = (await client.get("/api/movies?offset=1")).json()
        assert [m["id"] for m in lower["movies"]] == [155, 13]
        assert all(m["imdb_rating"] < 9.2 for m in lower["movies"])
        for rating in [0, 10.1, 7.65, "invalid"]:
            assert (await client.put("/api/preferences", json={**prefs, "imdb_rating": rating})).status_code == 422
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as client:
        assert (await client.get("/api/status")).json()["preferences"]["imdb_rating"] == 9.2
        for rating in [1, 6.9, 7.6, 10, None]:
            assert (await client.put("/api/preferences", json={**prefs, "imdb_rating": rating})).status_code == 200
        assert (await client.get("/api/movies")).json()["total"] == 4


async def test_series_selection_pagination_and_typed_history(tmp_path: Path, films: list[dict]) -> None:
    """Persist series selection and avoid collisions between film and series actions."""
    app = create_app(tmp_path)
    store = app.state.store
    store.set("providers", [{"provider_id": 8}])
    series = {**films[0], "media_type": "tv"}
    store.publish(
        [*films, series],
        {
            "provider_ids": [8],
            "media_types": ["movie", "tv"],
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        prefs = {"provider_ids": [8], "min_votes": 0, "media_type": "tv"}
        assert (await client.put("/api/preferences", json=prefs)).status_code == 200
        assert (await client.get("/api/movies")).json()["total"] == 1
        assert (await client.put("/api/titles/tv/238/state", json={"state": "watched"})).status_code == 200
        assert (await client.get("/api/movies")).json()["total"] == 0
        assert (await client.get("/api/movies?view=watched")).json()["total"] == 1
        await client.put("/api/preferences", json={**prefs, "media_type": "movie"})
        assert (await client.get("/api/movies")).json()["total"] == 4
        await client.put("/api/titles/tv/238/state", json={"state": "unseen"})
        assert (await client.put("/api/preferences", json={**prefs, "media_type": "all"})).status_code == 422
        first = (await client.get("/api/movies?limit=2")).json()
        second = (await client.get("/api/movies?limit=2&offset=2")).json()
        assert first["total"] == 4
        assert [(m["media_type"], m["id"]) for m in first["movies"] + second["movies"]] == [
            ("movie", 278),
            ("movie", 238),
            ("movie", 155),
            ("movie", 13),
        ]
        assert (await client.put("/api/titles/episode/238/state", json={"state": "hidden"})).status_code == 422
        assert (await client.put("/api/preferences", json={**prefs, "media_type": "episode"})).status_code == 422
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as client:
        assert (await client.get("/api/status")).json()["preferences"]["media_type"] == "movie"
        assert (await client.get("/api/movies")).json()["total"] == 4


async def test_previous_combined_selection_becomes_film_list(tmp_path: Path) -> None:
    """Migrate the removed combined option without changing other saved preferences."""
    app = create_app(tmp_path)
    saved = {"provider_ids": [8], "media_type": "all", "min_votes": 1000, "imdb_rating": 6.9}
    app.state.store.set("preferences", saved)
    reopened = create_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(reopened), base_url="http://test") as client:
        prefs = (await client.get("/api/status")).json()["preferences"]
        assert prefs["media_type"] == "movie"
        assert prefs["provider_ids"] == [8]
        assert prefs["min_votes"] == 1000
        assert prefs["imdb_rating"] == 6.9


async def test_default_filters(tmp_path: Path) -> None:
    """Start with English and the requested genre exclusions without a catalog."""
    async with AsyncClient(transport=ASGITransport(create_app(tmp_path)), base_url="http://test") as client:
        status = (await client.get("/api/status")).json()
        assert {g["id"] for g in status["genres"]} == {16, 99}
        prefs = status["preferences"]
        assert prefs["language"] == "en"
        assert prefs["excluded_genres"] == [16, 99]
        assert prefs["exclude_standup"] is True
        assert prefs["imdb_rating"] is None
