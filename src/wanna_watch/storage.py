"""Persist catalog snapshots and personal preferences in SQLite."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Store:
    """Maintain a single-user catalog without coupling history to refreshes."""

    path: Path

    def __init__(self, path: Path) -> None:
        """Create the database and schema at the given path.

        Args:
            path: Location of the personal SQLite database.
        """
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL CHECK (state IN ('watched', 'hidden'))
                );
            """)
            db.execute("BEGIN IMMEDIATE")
            for table, value_column in [("movies", "payload TEXT NOT NULL"), ("history", "state TEXT NOT NULL")]:
                columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                if "media_type" not in columns:
                    db.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy")
                    constraint = "CHECK (state IN ('watched', 'hidden'))" if table == "history" else ""
                    db.execute(
                        f"CREATE TABLE {table} (id INTEGER NOT NULL, {value_column} {constraint}, "
                        "media_type TEXT NOT NULL DEFAULT 'movie' CHECK (media_type IN ('movie', 'tv')), "
                        "PRIMARY KEY (media_type, id))"
                    )
                    db.execute(f"INSERT INTO {table} SELECT *, 'movie' FROM {table}_legacy")
                    db.execute(f"DROP TABLE {table}_legacy")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection, committing on success and rolling back on failure."""
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key: str, default: Any = None) -> Any:
        """Read a JSON setting, returning the default when absent.

        Args:
            key: Setting name.
            default: Value to use before the setting is saved.

        Returns:
            The decoded setting or default.
        """
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any) -> None:
        """Save a JSON setting.

        Args:
            key: Setting name.
            value: JSON-serializable setting value.
        """
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))

    def publish(
        self, movies: list[dict[str, Any]], metadata: dict[str, Any], *, genres: list[dict[str, Any]] | None = None
    ) -> None:
        """Atomically replace a fully collected catalog, retaining personal history.

        Args:
            movies: Complete enriched catalog to publish.
            metadata: Coverage counts, selected providers, and freshness timestamps.
            genres: Optional combined film/series genre directory published with the snapshot.
        """
        with self.connect() as db:
            db.execute("DELETE FROM movies")
            db.executemany(
                "INSERT INTO movies VALUES (?, ?, ?)",
                [(m["id"], json.dumps(m), m.get("media_type", "movie")) for m in movies],
            )
            db.execute("INSERT OR REPLACE INTO settings VALUES ('snapshot', ?)", (json.dumps(metadata),))
            if genres is not None:
                db.execute("INSERT OR REPLACE INTO settings VALUES ('genres', ?)", (json.dumps(genres),))

    def movies(
        self,
        providers: list[int],
        min_votes: int,
        view: str = "unseen",
        *,
        excluded_genres: list[int] | None = None,
        exclude_standup: bool = False,
        language: str = "all",
        after_year: int | None = None,
        imdb_rating: float | None = None,
        media_type: str = "movie",
    ) -> list[dict[str, Any]]:
        """Filter the entire snapshot and globally rank it by IMDb rating.

        Args:
            providers: Subscription provider IDs to include with OR semantics.
            min_votes: Minimum IMDb vote count.
            view: One of unseen, watched, or hidden.
            excluded_genres: Reject films matching any of these TMDB genre IDs.
            exclude_standup: Reject films tagged with TMDB's stand-up comedy keyword.
            language: Original-language code en/de/fr, other, or all.
            after_year: Exclusive release-year lower bound; None means any year.
            imdb_rating: Maximum IMDb rating, inclusive; None means any rating.
            media_type: movie, tv, or all; series are ranked as complete shows.

        Returns:
            Eligible titles ordered by rating, vote count, title, and stable ID.
        """
        selected = set(providers)
        with self.connect() as db:
            rows = db.execute(
                "SELECT m.payload, h.state FROM movies m LEFT JOIN history h "
                "ON m.id = h.id AND m.media_type = h.media_type"
            ).fetchall()
        result = []
        for payload, state in rows:
            movie = json.loads(payload)
            movie.setdefault("media_type", "movie")
            if media_type != "all" and movie["media_type"] != media_type:
                continue
            if (state or "unseen") != view or movie["imdb_votes"] < min_votes:
                continue
            if set(excluded_genres or []).intersection(g["id"] for g in movie.get("genres", [])):
                continue
            if exclude_standup and movie.get("is_standup"):
                continue
            if imdb_rating is not None and movie["imdb_rating"] > imdb_rating:
                continue
            original = movie.get("original_language")
            if language == "other" and (not original or original in {"en", "de", "fr"}):
                continue
            if language not in {"all", "other"} and original != language:
                continue
            year = str(movie.get("year") or "")
            if after_year is not None and (not year.isdigit() or int(year) <= after_year):
                continue
            movie["providers"] = [p for p in movie["providers"] if p["provider_id"] in selected]
            if movie["providers"]:
                result.append(movie)
        return sorted(
            result,
            key=lambda m: (-m["imdb_rating"], -m["imdb_votes"], m["title"].casefold(), m["media_type"], m["id"]),
        )

    def title(self, media_type: str, movie_id: int) -> dict[str, Any] | None:
        """Read one catalog title without applying personal filters.

        Args:
            media_type: Movie or TV identity namespace.
            movie_id: TMDB identifier.

        Returns:
            Stored title, or None when it is absent.
        """
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM movies WHERE media_type = ? AND id = ?", (media_type, movie_id)
            ).fetchone()
        return {**json.loads(row[0]), "media_type": media_type} if row else None

    def set_state(self, movie_id: int, state: str, media_type: str = "movie") -> None:
        """Mark a known title watched or hidden, or restore it to unseen.

        Args:
            movie_id: TMDB movie ID.
            state: unseen, watched, or hidden.
            media_type: movie or tv, separating overlapping TMDB IDs.

        Raises:
            ValueError: The state is invalid or the title is unknown.
        """
        if state not in {"unseen", "watched", "hidden"}:
            raise ValueError("Unknown watch state.")
        with self.connect() as db:
            if not db.execute(
                "SELECT 1 FROM movies WHERE id = ? AND media_type = ?", (movie_id, media_type)
            ).fetchone():
                raise ValueError("This title is not in the catalog.")
            if state == "unseen":
                db.execute("DELETE FROM history WHERE id = ? AND media_type = ?", (movie_id, media_type))
            else:
                db.execute("INSERT OR REPLACE INTO history VALUES (?, ?, ?)", (movie_id, state, media_type))
