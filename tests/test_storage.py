"""Exercise ranking, personal history, and atomic publication against actual SQLite."""

import sqlite3
from pathlib import Path

import pytest

from wanna_watch.storage import Store

pytestmark = pytest.mark.integration


def test_global_ranking_and_exact_imdb_vote_filter(store: Store, films: list[dict]) -> None:
    """Rank the whole catalog, regardless of ingestion order, using IMDb votes."""
    store.publish(films, {"complete": True})
    assert [m["id"] for m in store.movies([8], 0)] == [278, 238, 155, 13]
    assert [m["id"] for m in store.movies([8], 3_000_000)] == [278, 155]
    assert store.movies([9], 0) == []
    assert store.movies([], 0) == []


def test_vote_threshold_is_inclusive(store: Store, films: list[dict]) -> None:
    """Include a title whose IMDb vote count equals the threshold exactly."""
    store.publish(films, {})
    assert 278 in [m["id"] for m in store.movies([8], 3236712)]
    assert store.movies([8], 3236713) == []


def test_history_survives_refresh_and_database_reopen(store: Store, films: list[dict]) -> None:
    """Keep watched and hidden history when titles leave and later rejoin a catalog."""
    store.publish(films, {})
    store.set_state(278, "watched")
    store.set_state(238, "hidden")
    store.publish([], {})
    store.publish(films, {})
    reopened = Store(store.path)
    assert [m["id"] for m in reopened.movies([8], 0)] == [155, 13]
    assert [m["id"] for m in reopened.movies([8], 0, "watched")] == [278]
    assert [m["id"] for m in reopened.movies([8], 0, "hidden")] == [238]
    reopened.set_state(278, "unseen")
    assert reopened.movies([8], 0)[0]["id"] == 278


def test_failed_publication_preserves_previous_snapshot(store: Store, films: list[dict]) -> None:
    """Roll back both catalog deletion and inserts when publication fails midway."""
    store.publish(films, {"version": 1})
    with pytest.raises(sqlite3.IntegrityError):
        store.publish([films[0], films[0]], {"version": 2})
    assert len(store.movies([8], 0)) == 4
    assert store.get("snapshot") == {"version": 1}


def test_invalid_state_and_unknown_film_leave_history_unchanged(store: Store, films: list[dict]) -> None:
    """Validate all state mutations before writing personal history."""
    store.publish(films, {})
    with pytest.raises(ValueError, match="Unknown watch state"):
        store.set_state(278, "deleted")
    with pytest.raises(ValueError, match="not in the catalog"):
        store.set_state(999999999, "watched")
    assert len(store.movies([8], 0)) == 4


def test_provider_filter_does_not_mutate_snapshot(store: Store, films: list[dict]) -> None:
    """Display only selected offers without deleting other subscriptions from storage."""
    films[0]["providers"].append({"provider_id": 9, "provider_name": "Amazon Prime Video"})
    store.publish(films, {})
    assert len(store.movies([9], 0)) == 1
    assert len(store.movies([8, 9], 0)[1]["providers"]) == 2


@pytest.mark.parametrize(
    ("language", "expected"),
    [("all", [278, 238, 155, 13]), ("en", [238]), ("de", [155]), ("fr", [278]), ("other", [13])],
)
def test_original_language_groups(store: Store, films: list[dict], language: str, expected: list[int]) -> None:
    """Exercise language groups with controlled filter inputs, including other languages."""
    for film, original in zip(films, ["en", "de", "fr", "ja"], strict=True):
        film["original_language"] = original
    store.publish(films, {})
    assert [m["id"] for m in store.movies([8], 0, language=language)] == expected


def test_unknown_language_is_not_assumed_to_be_other(store: Store, films: list[dict]) -> None:
    """Include missing language only when no language restriction is active."""
    for film in films:
        film.pop("original_language", None)
    store.publish(films, {})
    assert len(store.movies([8], 0)) == 4
    assert store.movies([8], 0, language="other") == []
    assert store.movies([8], 0, language="en") == []


def test_year_boundary_missing_year_and_combined_exclusions(store: Store, films: list[dict]) -> None:
    """Combine exclusive year bounds and any-genre exclusion before ranking and history filtering."""
    for film, year in zip(films, ["1990", "1991", "2000", ""], strict=True):
        film["year"] = year
    films[1]["genres"] = [{"id": 35, "name": "Comedy"}, {"id": 16, "name": "Animation"}]
    films[2]["genres"] = [{"id": 35, "name": "Comedy"}]
    films[2]["is_standup"] = True
    store.publish(films, {})
    assert [m["id"] for m in store.movies([8], 0, after_year=1990)] == [278, 155]
    assert [m["id"] for m in store.movies([8], 0, after_year=1990, excluded_genres=[16, 99])] == [278]
    assert [m["id"] for m in store.movies([8], 0, after_year=1990, exclude_standup=True)] == [155]
    assert store.movies([8], 0, after_year=1990, excluded_genres=[16], exclude_standup=True) == []
    store.set_state(155, "watched")
    assert store.movies([8], 0, "watched", excluded_genres=[16]) == []
    assert len(store.movies([8], 0, "watched", after_year=1990)) == 1
    assert len(store.movies([8], 0, "watched", exclude_standup=True)) == 1


def test_maximum_rating_combines_with_filters_and_history(store: Store, films: list[dict]) -> None:
    """Include the maximum and lower ratings while retaining vote and history filters."""
    store.publish(films, {})
    assert [m["id"] for m in store.movies([8], 0, imdb_rating=9.2)] == [238, 155, 13]
    assert [m["id"] for m in store.movies([8], 3_000_000, imdb_rating=9.2)] == [155]
    assert store.movies([8], 0, imdb_rating=7.6) == []
    assert len(store.movies([8], 0, imdb_rating=None)) == 4
    store.set_state(238, "watched")
    assert [m["id"] for m in store.movies([8], 0, imdb_rating=9.2)] == [155, 13]
    assert [m["id"] for m in store.movies([8], 0, "watched", imdb_rating=9.2)] == [238]


def test_overlapping_film_and_series_ids_have_independent_history(store: Store, films: list[dict]) -> None:
    """Keep media identities distinct through filtering, refresh, and restore."""
    series = {**films[0], "media_type": "tv"}
    store.publish([films[0], series], {})
    assert len(store.movies([8], 0, media_type="all")) == 2
    store.set_state(series["id"], "watched", "tv")
    assert len(store.movies([8], 0, media_type="movie")) == 1
    assert store.movies([8], 0, media_type="tv") == []
    assert len(store.movies([8], 0, "watched", media_type="tv")) == 1
    store.set_state(series["id"], "hidden")
    store.publish([series, films[0]], {})
    store.set_state(series["id"], "unseen", "tv")
    assert len(store.movies([8], 0, media_type="tv")) == 1
    assert len(store.movies([8], 0, "hidden")) == 1


def test_existing_film_database_migrates_without_losing_history(tmp_path: Path, films: list[dict]) -> None:
    """Upgrade the previous schema transactionally and leave removed-title history intact."""
    import json

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE movies (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE history (id INTEGER PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        db.execute("INSERT INTO movies VALUES (?, ?)", (238, json.dumps(films[0])))
        db.execute("INSERT INTO history VALUES (238, 'watched')")
        db.execute("INSERT INTO history VALUES (999, 'hidden')")
        db.execute("INSERT INTO settings VALUES ('preferences', ?)", (json.dumps({"provider_ids": [8]}),))
    migrated = Store(path)
    assert migrated.movies([8], 0, "watched")[0]["id"] == 238
    assert migrated.get("preferences") == {"provider_ids": [8]}
    with migrated.connect() as db:
        assert db.execute("SELECT state FROM history WHERE id=999 AND media_type='movie'").fetchone() == ("hidden",)
    assert Store(path).movies([8], 0, "watched")[0]["id"] == 238
