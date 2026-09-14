"""Audit the actual configured subscriptions and collected films against live sources."""

import os
from pathlib import Path

import pytest

from wanna_watch.app import read_token
from wanna_watch.storage import Store
from wanna_watch.tmdb import TMDB
from wanna_watch.verify import verify

pytestmark = pytest.mark.live


def test_configured_subscriptions_exist_in_germany() -> None:
    """Check selected IDs against the authenticated German provider directory."""
    directory = Path(os.getenv("WANNA_WATCH_DATA_DIR", "data"))
    store = Store(directory / "wanna-watch.sqlite3")
    selected = store.get("preferences", {}).get("provider_ids", [])
    token = read_token()
    if not token or not selected:
        pytest.skip("Configure a real TMDB token and select subscriptions before live testing.")
    source = TMDB(token)
    try:
        available = {provider["provider_id"] for provider in source.providers()}
        assert set(selected).issubset(available)
    finally:
        source.close()


def test_real_catalog_passes_imdb_and_availability_audit() -> None:
    """Re-check all eligible IMDb scores and ten actual German subscription offers."""
    directory = Path(os.getenv("WANNA_WATCH_DATA_DIR", "data"))
    store = Store(directory / "wanna-watch.sqlite3")
    if not read_token() or not store.get("snapshot"):
        pytest.skip("Complete a real catalog refresh before running the source audit.")
    report = verify(directory, limit=10)
    assert report["passed"], report["failures"]
    assert report["eligible_films_checked_against_imdb"] > 0
    assert report["live_availability_sample"]


def test_real_refresh_publishes_genres_language_and_standup(tmp_path: Path) -> None:
    """Refresh the smallest configured real catalog into an isolated database with metadata."""
    from wanna_watch.catalog import refresh_catalog

    directory = Path(os.getenv("WANNA_WATCH_DATA_DIR", "data"))
    personal = Store(directory / "wanna-watch.sqlite3")
    snapshot = personal.get("snapshot")
    if not read_token() or not snapshot:
        pytest.skip("Configure and refresh real subscriptions before checking enrichment.")
    counts = snapshot["provider_counts"].get("movie", snapshot["provider_counts"])
    provider = int(min(counts, key=lambda key: counts[key]))
    isolated = Store(tmp_path / "catalog.sqlite3")
    source = TMDB(read_token())
    try:
        metadata = refresh_catalog(source, isolated, directory, [provider], lambda message: None)
        movies = isolated.movies([provider], 0, media_type="all")
        assert metadata["ranked"] == len(movies) > 0
        assert isolated.get("genres")
        assert {m["media_type"] for m in movies} == {"movie", "tv"}
        shows = isolated.movies([provider], 0, media_type="tv")
        assert all(m["watch_url"].startswith("https://www.themoviedb.org/tv/") for m in shows)
        assert any(m["number_of_seasons"] for m in shows)
        assert all(isinstance(m["genres"], list) for m in movies)
        assert all(isinstance(m["is_standup"], bool) for m in movies)
        assert any(m["original_language"] == "en" for m in movies)
        assert any(m["genres"] for m in movies)
        assert all(m["original_language"] == "en" for m in isolated.movies([provider], 0, language="en"))
    finally:
        source.close()
