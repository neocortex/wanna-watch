"""Check conservative audio decisions and real SQLite cache integration."""

import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wanna_watch.app import create_app
from wanna_watch.audio import AudioWarnings, missing_english_services
from wanna_watch.storage import Store


@pytest.mark.parametrize(
    ("editions", "expected"),
    [
        ([["deu"]], ["prime"]),
        ([["eng"]], []),
        ([["deu", "und"]], []),
        ([["mul"]], []),
        ([["zxx"]], []),
        ([[]], []),
        ([["deu"], ["eng"]], []),
        ([["deu"], []], []),
        ([["deu"], ["fra"]], ["prime"]),
        ([], []),
    ],
)
def test_subscription_audio_boundaries(editions: list[list[str]], expected: list[str]) -> None:
    """Warn only when every reported subscription edition omits English."""
    offers = [
        {"service": {"id": "prime"}, "type": "subscription", "audios": [{"language": code} for code in codes]}
        for codes in editions
    ]
    assert missing_english_services({"streamingOptions": {"de": offers}}) == expected


@pytest.mark.parametrize("kind", ["rent", "buy", "addon", "free"])
def test_ignore_other_offer_types(kind: str) -> None:
    """Do not transfer German-only rental/channel audio onto a base subscription."""
    offer = {"service": {"id": "prime"}, "type": kind, "audios": [{"language": "deu"}]}
    assert missing_english_services({"streamingOptions": {"de": [offer]}}) == []
    offer.update(type="subscription", addon={"id": "channel"})
    assert missing_english_services({"streamingOptions": {"de": [offer]}}) == []
    assert missing_english_services({"streamingOptions": {"us": [offer]}}) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_audio_cache_routes_and_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise HTTP and persistent cache boundaries without upstream API substitutions."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STREAMING_AVAILABILITY_API_KEY", "test-cache-only")
    app = create_app(tmp_path)
    store = app.state.store
    # Reason: boundary inputs exercise cache interpretation, not real availability claims.
    movie = {
        "id": 45269,
        "media_type": "movie",
        "imdb_id": "tt1504320",
        "original_language": "en",
        "providers": [{"provider_id": 9}, {"provider_id": 8}],
        "title": "The King's Speech",
        "imdb_votes": 1,
        "imdb_rating": 8.0,
    }
    store.publish([movie, {**movie, "media_type": "tv"}], {})
    cache = {"imdb_id": movie["imdb_id"], "checked_at": time.time(), "services": ["prime"]}
    store.set("audio:de:movie/45269", cache)
    store.set("audio:retry_after", time.time() + 3600)
    store.set("preferences", {"provider_ids": [9], "min_votes": 0})
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        page = (await client.get("/api/movies")).json()
        assert page["movies"][0]["audio_warning_provider_ids"] == [9]
        assert (await client.get("/api/titles/movie/45269/audio")).json() == {"provider_ids": [9]}
        assert (await client.get("/api/titles/tv/45269/audio")).json() == {"provider_ids": []}
        assert (await client.get("/api/titles/movie/999/audio")).status_code == 404
        assert (await client.get("/api/titles/invalid/45269/audio")).status_code == 422
    audio = AudioWarnings(Store(store.path))
    with audio.lock:
        assert audio.cached(movie) == [9]
    assert audio.providers(movie) == [9]
    assert audio.providers({**movie, "original_language": "de"}) == []
    assert audio.providers({**movie, "imdb_id": "tt0137523"}) == []
    assert audio.providers({**movie, "providers": [{"provider_id": 119}]}) == []
    store.set("audio:de:movie/45269", {**cache, "checked_at": time.time() - 86401})
    assert audio.cached(movie) is None
    assert audio.providers(movie) == []
    monkeypatch.delenv("STREAMING_AVAILABILITY_API_KEY")
    store.set("audio:de:movie/45269", cache)
    assert audio.providers(movie) == []
