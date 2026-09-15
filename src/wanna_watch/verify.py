"""Independently audit a saved catalog against IMDb and current German subscription offers."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from wanna_watch.app import Preferences, read_token
from wanna_watch.catalog import subscription_offers
from wanna_watch.imdb import download_ratings, match_ratings
from wanna_watch.storage import Store
from wanna_watch.tmdb import TMDB, SourceError


def verify(directory: Path, limit: int = 10) -> dict:
    """Check global ranking and re-fetch a sample's actual upstream availability.

    Args:
        directory: App data directory containing the real saved snapshot.
        limit: Number of highest-ranked unseen films to re-check live.

    Returns:
        Timestamped evidence report, including mismatches and coverage.

    Raises:
        ValueError: No current catalog or eligible titles are available.
        SourceError: TMDB cannot be queried with the configured credential.
    """
    store = Store(directory / "wanna-watch.sqlite3")
    snapshot = store.get("snapshot")
    saved_preferences = store.get("preferences", {"provider_ids": []})
    audit_type = saved_preferences.get("media_type", "movie")
    # Reason: the audit can cover both catalogs even though the browser exposes separate lists.
    prefs = Preferences(**{**saved_preferences, "media_type": "movie"}).model_dump()
    prefs["media_type"] = audit_type
    if not snapshot:
        raise ValueError("No catalog exists. Choose subscriptions and complete a refresh first.")
    if not set(prefs["provider_ids"]).issubset(snapshot["provider_ids"]):
        raise ValueError("Refresh the catalog to cover all selected subscriptions before verifying.")
    if prefs["media_type"] != "movie" and "tv" not in snapshot.get("media_types", []):
        raise ValueError("Refresh the catalog to collect series before verifying this selection.")
    services = prefs.pop("service_ids")
    selected = set(prefs["provider_ids"] if services is None else services).intersection(prefs["provider_ids"])
    filters = {key: value for key, value in prefs.items() if key != "provider_ids"}
    movies = store.movies(providers=sorted(selected), **filters)
    if not movies:
        raise ValueError("No unseen films match the current filters.")
    source = TMDB(read_token())
    failures = []
    sample = []
    try:
        with store.connect() as db:
            rows = db.execute(
                "SELECT m.payload, h.state FROM movies m LEFT JOIN history h ON m.id = h.id "
                "AND m.media_type = h.media_type"
            ).fetchall()
        eligible = []
        for payload, state in rows:
            saved = json.loads(payload)
            saved.setdefault("media_type", "movie")
            if prefs["media_type"] != "all" and saved["media_type"] != prefs["media_type"]:
                continue
            if prefs["imdb_rating"] is not None and saved["imdb_rating"] > prefs["imdb_rating"]:
                continue
            genre_ids = [genre["id"] for genre in saved.get("genres", [])]
            if any(genre in prefs["excluded_genres"] for genre in genre_ids):
                continue
            if prefs["exclude_standup"] and saved.get("is_standup", False):
                continue
            original = saved.get("original_language")
            wanted = prefs["language"]
            if wanted == "other":
                if original is None or original == "" or original in ("en", "de", "fr"):
                    continue
            elif wanted != "all" and wanted != original:
                continue
            if prefs["after_year"] is not None:
                year = str(saved.get("year") or "")
                if not year.isdecimal() or int(year) < prefs["after_year"] + 1:
                    continue
            if state is None and saved["imdb_votes"] >= prefs["min_votes"]:
                if selected.intersection(p["provider_id"] for p in saved["providers"]):
                    eligible.append(saved)
        expected = sorted(
            eligible,
            key=lambda m: (-m["imdb_rating"], -m["imdb_votes"], m["title"].casefold(), m["media_type"], m["id"]),
        )
        if [(m["media_type"], m["id"]) for m in movies] != [(m["media_type"], m["id"]) for m in expected]:
            failures.append("Displayed films differ from the complete eligible catalog or its IMDb ordering.")
        if len(rows) != snapshot["ranked"] or (
            len(rows) + snapshot["without_subscription_offer"] + snapshot["without_imdb_rating"]
            != snapshot["discovered"]
        ):
            failures.append("Catalog row counts do not reconcile with the published coverage report.")
        path, modified = download_ratings(directory)
        ratings = match_ratings(path, {movie["imdb_id"] for movie in movies})
        if len({(m["media_type"], m["id"]) for m in movies}) != len(movies):
            failures.append("Catalog deduplication failed.")
        for movie in movies:
            if ratings.get(movie["imdb_id"]) != (movie["imdb_rating"], movie["imdb_votes"]):
                failures.append(f"IMDb rating or vote count changed for {movie['title']}; refresh needed.")
            if not movie["providers"] or not {p["provider_id"] for p in movie["providers"]}.issubset(selected):
                failures.append(f"Displayed subscription offers do not match the selection for {movie['title']}.")
        sample_movies = [
            movie for kind in ("movie", "tv") for movie in [m for m in movies if m["media_type"] == kind][:limit]
        ]
        for movie in sample_movies:
            live = source.series(movie["id"]) if movie["media_type"] == "tv" else source.movie(movie["id"])
            offers = subscription_offers(live, set(prefs["provider_ids"]))
            if live.get("imdb_id") != movie["imdb_id"] or not offers:
                failures.append(f"Identity or German subscription availability mismatch: {movie['title']}.")
            if {g["id"] for g in live["genres"]} != {g["id"] for g in movie.get("genres", [])}:
                failures.append(f"Genre metadata mismatch: {movie['title']}.")
            if live.get("original_language") != movie.get("original_language"):
                failures.append(f"Original-language metadata mismatch: {movie['title']}.")
            tagged_standup = any(k["id"] == 9716 for k in live["keywords"]["keywords"])
            if tagged_standup != movie.get("is_standup"):
                failures.append(f"Stand-up classification mismatch: {movie['title']}.")
            sample.append(
                {
                    "title": movie["title"],
                    "tmdb_id": movie["id"],
                    "media_type": movie["media_type"],
                    "imdb_id": movie["imdb_id"],
                    "imdb_rating": movie["imdb_rating"],
                    "imdb_votes": movie["imdb_votes"],
                    "live_german_subscriptions": [p["provider_name"] for p in offers],
                    "watch_url": movie["watch_url"],
                }
            )
    finally:
        source.close()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "snapshot": snapshot,
        "ratings_modified": modified,
        "eligible_films_checked_against_imdb": len(movies),
        "live_availability_sample": sample,
        "failures": failures,
        "passed": not failures,
        "scope": "Source checks only. Confirm playback and account entitlement in the streaming service.",
    }
    (directory / "verification.json").write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    """Run the audit and exit unsuccessfully if the source checks fail."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    try:
        report = verify(Path(os.getenv("WANNA_WATCH_DATA_DIR", "data")), args.limit)
    except (ValueError, SourceError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
