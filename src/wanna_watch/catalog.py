"""Build an auditable IMDb-ranked snapshot from complete German subscription discovery."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wanna_watch.imdb import download_ratings, match_ratings
from wanna_watch.storage import Store
from wanna_watch.tmdb import TMDB


def subscription_offers(movie: dict[str, Any], selected: set[int]) -> list[dict[str, Any]]:
    """Keep only the selected providers' subscription offers in Germany.

    Args:
        movie: Real TMDB movie details including watch/providers.
        selected: Exact subscription provider IDs.

    Returns:
        Matching flatrate offers; rental, purchase, and other countries are excluded.
    """
    german = movie["watch/providers"]["results"].get("DE", {})
    return [p for p in german.get("flatrate", []) if p["provider_id"] in selected]


def refresh_catalog(
    source: TMDB, store: Store, directory: Path, selected: list[int], progress: Callable[[str], None]
) -> dict[str, Any]:
    """Collect, enrich, validate, and atomically publish the selected catalog.

    Args:
        source: Authenticated real TMDB client.
        store: Personal database.
        directory: IMDb download cache.
        selected: Subscription provider IDs selected by the user.
        progress: Callback to report the current collection phase.

    Returns:
        Published coverage and freshness metadata.

    Raises:
        ValueError: No subscription has been selected.
    """
    if not selected:
        raise ValueError("Choose at least one subscription first.")
    started = datetime.now(UTC).isoformat()
    progress("Downloading the official IMDb ratings dataset…")
    ratings_path, ratings_modified = download_ratings(directory)
    store.set("providers", source.providers())
    store.set("providers_date", datetime.now(UTC).date().isoformat())
    provider_counts = {}
    details = []
    genres = {}
    discovered = 0
    for media_type in ("movie", "tv"):
        ids: set[int] = set()
        counts = {}
        for provider in selected:
            progress(f"Collecting {media_type} subscription {provider}…")
            found = source.discover(provider, progress, media_type=media_type)
            counts[str(provider)] = len(found)
            ids.update(found)
        provider_counts[media_type] = counts
        discovered += len(ids)
        for genre in source.get(f"genre/{media_type}/list", language="en-US")["genres"]:
            genres[genre["id"]] = genre
        fetch = source.series if media_type == "tv" else source.movie
        with ThreadPoolExecutor(max_workers=6) as pool:
            for index, movie in enumerate(pool.map(fetch, sorted(ids)), 1):
                movie["media_type"] = media_type
                details.append(movie)
                progress(f"Checking German offers and IMDb IDs: {index:,} of {len(ids):,} {media_type} titles")
    progress("Matching exact IMDb IDs and ranking the complete catalog…")
    ratings = match_ratings(ratings_path, {m["imdb_id"] for m in details if m.get("imdb_id")})
    movies = []
    unavailable = 0
    unrated = 0
    for movie in details:
        offers = subscription_offers(movie, set(selected))
        if not offers:
            unavailable += 1
            continue
        rating = ratings.get(movie.get("imdb_id"))
        if rating is None:
            unrated += 1
            continue
        movies.append(
            {
                "id": movie["id"],
                "media_type": movie["media_type"],
                "number_of_seasons": movie.get("number_of_seasons"),
                "number_of_episodes": movie.get("number_of_episodes"),
                "status": movie.get("status"),
                "title": movie["title"],
                "year": (movie.get("release_date") or "")[:4],
                "runtime": movie.get("runtime"),
                "genres": movie.get("genres", []),
                "original_language": movie.get("original_language") or None,
                "is_standup": any(k["id"] == 9716 for k in movie["keywords"]["keywords"]),
                "overview": movie.get("overview", ""),
                "poster_path": movie.get("poster_path"),
                "imdb_id": movie["imdb_id"],
                "imdb_rating": rating[0],
                "imdb_votes": rating[1],
                "providers": offers,
                "watch_url": f"https://www.themoviedb.org/{movie['media_type']}/{movie['id']}/watch?locale=DE",
            }
        )
    metadata = {
        "started_at": started,
        "completed_at": datetime.now(UTC).isoformat(),
        "ratings_modified": ratings_modified,
        "provider_ids": selected,
        "provider_counts": provider_counts,
        "media_types": ["movie", "tv"],
        "discovered": discovered,
        "ranked_by_type": {kind: sum(m["media_type"] == kind for m in movies) for kind in ("movie", "tv")},
        "ranked": len(movies),
        "without_subscription_offer": unavailable,
        "without_imdb_rating": unrated,
        "region": "DE",
    }
    store.publish(movies, metadata, genres=sorted(genres.values(), key=lambda genre: genre["name"]))
    progress(f"Ready. {len(movies):,} films and series ranked by IMDb.")
    return metadata
