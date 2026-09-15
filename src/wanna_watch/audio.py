"""Supplement German subscription offers with optional, cached audio warnings."""

import os
import threading
import time
from typing import Any

import httpx
from dotenv import dotenv_values

from wanna_watch.storage import Store

# Reason: exact base subscriptions must not inherit rental, channel, or ad-tier audio.
SERVICES = {8: "netflix", 9: "prime", 337: "disney"}
CACHE_SECONDS = 86400


def missing_english_services(show: dict[str, Any]) -> list[str]:
    """Find subscriptions whose reported audio options all omit English.

    Args:
        show: Streaming Availability API show response for Germany.

    Returns:
        Service IDs with nonempty audio lists on every subscription offer and no English.
        Unknown offers and mixed English/non-English editions do not trigger warnings.
    """
    grouped: dict[str, list[set[str]]] = {}
    for offer in show.get("streamingOptions", {}).get("de", []):
        service = offer["service"]["id"]
        if service not in SERVICES.values() or offer["type"] != "subscription" or offer.get("addon"):
            continue
        languages = {audio["language"] for audio in offer.get("audios", [])}
        if languages.intersection({"", "und", "mul", "zxx", None}):
            languages = set()
        grouped.setdefault(service, []).append(languages)
    return sorted(
        service
        for service, editions in grouped.items()
        if all(languages and not languages.intersection({"eng", "en"}) for languages in editions)
    )


class AudioWarnings:
    """Look up visible English titles without delaying or modifying the catalog."""

    store: Store
    lock: threading.Lock
    next_request: float

    def __init__(self, store: Store) -> None:
        """Initialize serialized requests and persistent cache access.

        Args:
            store: Personal SQLite store, shared with the catalog.
        """
        self.store = store
        self.lock = threading.Lock()
        self.next_request = 0.0

    def cached(self, movie: dict[str, Any]) -> list[int] | None:
        """Read fresh warnings without waiting for upstream requests.

        Args:
            movie: Stored title including typed identity and subscription providers.

        Returns:
            Provider IDs, an empty list for ineligible titles, or None for a cache miss.
        """
        if movie.get("original_language") != "en":
            return []
        selected = {p["provider_id"] for p in movie["providers"]}.intersection(SERVICES)
        if not selected or not movie.get("imdb_id"):
            return []
        cached = self.store.get(f"audio:de:{movie['media_type']}/{movie['id']}")
        if not cached or cached["imdb_id"] != movie["imdb_id"]:
            return None
        if time.time() - cached["checked_at"] >= CACHE_SECONDS:
            return None
        return sorted(provider for provider in selected if SERVICES[provider] in cached["services"])

    def providers(self, movie: dict[str, Any]) -> list[int]:
        """Return provider IDs whose subscription audio may omit English.

        Args:
            movie: Stored title including identity, original language, and providers.

        Returns:
            Matching TMDB provider IDs, or an empty list when unavailable or unconfigured.
        """
        key = (
            os.getenv("STREAMING_AVAILABILITY_API_KEY")
            or dotenv_values(".env").get("STREAMING_AVAILABILITY_API_KEY")
            or ""
        ).strip()
        selected = {p["provider_id"] for p in movie["providers"]}.intersection(SERVICES)
        if not key or movie.get("original_language") != "en" or not selected or not movie.get("imdb_id"):
            return []
        cached_providers = self.cached(movie)
        if cached_providers is not None:
            return cached_providers
        identity = f"{movie['media_type']}/{movie['id']}"
        cache_key = f"audio:de:{identity}"
        with self.lock:
            now = time.time()
            cached = self.store.get(cache_key)
            if cached and cached["imdb_id"] == movie["imdb_id"] and now - cached["checked_at"] < CACHE_SECONDS:
                services = cached["services"]
            else:
                if now < self.store.get("audio:retry_after", 0):
                    return []
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + 1
                try:
                    response = httpx.get(
                        f"https://api.movieofthenight.com/v4/shows/{movie['imdb_id']}",
                        params={"country": "de"},
                        headers={"X-API-Key": key},
                        timeout=8,
                    )
                    if response.status_code == 404:
                        services = []
                    else:
                        response.raise_for_status()
                        show = response.json()
                        if show["imdbId"] != movie["imdb_id"] or show["tmdbId"] != identity:
                            return []
                        services = missing_english_services(show)
                except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
                    # Reason: quota/auth/network failures must not break browsing or retry on every card.
                    self.store.set("audio:retry_after", time.time() + 3600)
                    return []
                self.store.set(
                    cache_key, {"imdb_id": movie["imdb_id"], "checked_at": time.time(), "services": services}
                )
        return sorted(provider for provider in selected if SERVICES[provider] in services)
