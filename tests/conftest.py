"""Share real IMDb source rows and isolated SQLite stores across tests."""

from pathlib import Path

import pytest

from wanna_watch.storage import Store


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous HTTP integration tests on asyncio."""
    return "asyncio"


@pytest.fixture
def store(tmp_path: Path) -> Store:
    """Create a real isolated database for storage and application tests."""
    return Store(tmp_path / "catalog.sqlite3")


@pytest.fixture
def films() -> list[dict]:
    """Provide real IMDb identities and ratings with explicit test-only offer inputs.

    The ratings were read from IMDb's official September 13, 2026 dataset.
    Provider membership here exercises filtering; it is not a live availability claim.
    These records are never loaded into the running application.
    """
    source_rows = [
        (238, "The Godfather", "tt0068646", 9.2, 2255117),
        (155, "The Dark Knight", "tt0468569", 9.1, 3225193),
        (278, "The Shawshank Redemption", "tt0111161", 9.3, 3236712),
        (13, "Forrest Gump", "tt0109830", 8.8, 2533690),
    ]
    return [
        {
            "id": movie_id,
            "title": title,
            "imdb_id": imdb_id,
            "imdb_rating": rating,
            "imdb_votes": votes,
            "providers": [{"provider_id": 8, "provider_name": "Netflix"}],
            "year": "",
            "runtime": None,
            "original_language": "en",
            "overview": "",
            "poster_path": None,
        }
        for movie_id, title, imdb_id, rating, votes in source_rows
    ]
