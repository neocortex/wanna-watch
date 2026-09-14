"""Access real German TMDB subscription catalogs with bounded retries and complete pagination."""

import threading
import time
from collections.abc import Callable
from typing import Any

import httpx


class SourceError(RuntimeError):
    """Report an upstream failure without leaking credentials or publishing partial data."""


class TMDB:
    """Use a shared HTTP client for discovery and movie enrichment."""

    client: httpx.Client
    lock: threading.Lock
    next_request: float

    def __init__(self, token: str) -> None:
        """Configure application authentication and request pacing.

        Args:
            token: TMDB API Read Access Token.

        Raises:
            SourceError: No credential has been configured.
        """
        if not token:
            raise SourceError("Add TMDB_READ_TOKEN to .env before loading subscriptions or refreshing.")
        self.client = httpx.Client(
            base_url="https://api.themoviedb.org/3/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=40,
        )
        self.lock = threading.Lock()
        self.next_request = 0

    def close(self) -> None:
        """Release HTTP connections after a catalog operation."""
        self.client.close()

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        """Fetch JSON with retries for temporary upstream failures.

        Args:
            path: Relative TMDB API path.
            **params: Query parameters.

        Returns:
            Decoded TMDB JSON object.

        Raises:
            SourceError: Authentication, network, or upstream response failure.
        """
        for attempt in range(4):
            with self.lock:
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + 0.06
            try:
                response = self.client.get(path, params=params)
            except httpx.RequestError:
                if attempt == 3:
                    raise SourceError("TMDB could not be reached. Your previous catalog is unchanged.") from None
                time.sleep(2**attempt)
                continue
            if response.status_code in {401, 403}:
                raise SourceError("TMDB rejected the token. Check TMDB_READ_TOKEN in .env.")
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(2**attempt)
                continue
            if response.is_error:
                raise SourceError(f"TMDB returned HTTP {response.status_code}. No partial catalog was saved.")
            return response.json()
        raise SourceError("TMDB is busy. Try refreshing later; your previous catalog is unchanged.")

    def providers(self) -> list[dict[str, Any]]:
        """Return real provider names and IDs available in Germany.

        Returns:
            TMDB provider objects ordered for Germany.
        """
        by_id = {}
        for media_type in ("movie", "tv"):
            for provider in self.get(f"watch/providers/{media_type}", watch_region="DE", language="en-US")["results"]:
                by_id.setdefault(provider["provider_id"], provider)
        result = list(by_id.values())
        return sorted(result, key=lambda p: (p.get("display_priority", 999), p["provider_name"]))

    def discover(
        self,
        provider_id: int | None,
        progress: Callable[[str], None],
        *,
        media_type: str = "movie",
        keyword_id: int | None = None,
        metadata: dict[int, dict[str, Any]] | None = None,
    ) -> set[int]:
        """Collect all discoverable titles of one type for a German subscription provider.

        Args:
            provider_id: Actual provider ID, or None for discovery without a provider restriction.
            progress: Callback for user-visible collection progress.
            media_type: movie or tv discovery.
            keyword_id: Optional TMDB keyword to require.
            metadata: Optional destination for the returned discovery metadata.

        Returns:
            Deduplicated movie IDs after all pages have been retrieved.

        Raises:
            SourceError: Pagination cannot establish full coverage.
        """
        params = {
            "include_adult": "false",
            "sort_by": "first_air_date.asc" if media_type == "tv" else "primary_release_date.asc",
        }

        if media_type == "tv":
            params["include_null_first_air_dates"] = "true"
        if provider_id is not None:
            params.update(
                watch_region="DE", with_watch_providers=provider_id, with_watch_monetization_types="flatrate"
            )
        if keyword_id is not None:
            params["with_keywords"] = keyword_id

        def remember(result: dict[str, Any]) -> None:
            """Retain source metadata when requested by a catalog migration."""
            if metadata is not None:
                metadata.update((movie["id"], movie) for movie in result["results"])

        def collect(lower: int, upper: int) -> set[int]:
            """Partition oversized catalogs by TMDB vote count before paging."""
            query = {**params, "vote_count.gte": lower, "vote_count.lte": upper}
            first = self.get(f"discover/{media_type}", **query, page=1)
            pages = first["total_pages"]
            if pages > 500:
                if lower == upper:
                    raise SourceError("A catalog exceeds TMDB's page limit; completeness could not be established.")
                middle = (lower + upper) // 2
                ids = collect(lower, middle) | collect(middle + 1, upper)
            else:
                remember(first)
                ids = {movie["id"] for movie in first["results"]}
                for page in range(2, pages + 1):
                    progress(f"Collecting {media_type} subscription {provider_id}: page {page} of {pages}")
                    result = self.get(f"discover/{media_type}", **query, page=page)
                    if result["total_results"] != first["total_results"]:
                        raise SourceError("The provider catalog changed during collection. Please refresh again.")
                    remember(result)
                    ids.update(movie["id"] for movie in result["results"])
            if len(ids) != first["total_results"]:
                raise SourceError("TMDB pagination returned duplicate or missing films. Please refresh again.")
            return ids

        # Reason: an effectively unbounded upper limit includes unrated titles (zero votes), too.
        return collect(0, 2_147_483_647)

    def movie(self, movie_id: int) -> dict[str, Any]:
        """Fetch movie metadata, IMDb identity, and current country-specific offers.

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Movie details with an appended watch/providers response.
        """
        return self.get(f"movie/{movie_id}", append_to_response="watch/providers,keywords", language="en-US")

    def series(self, series_id: int) -> dict[str, Any]:
        """Fetch a complete show's identity, metadata, and German provider offers.

        Args:
            series_id: TMDB TV series ID, independent of movie IDs.

        Returns:
            Details with the series-level IMDb ID and normalized metadata keys.
        """
        result = self.get(
            f"tv/{series_id}", append_to_response="watch/providers,keywords,external_ids", language="en-US"
        )
        result["imdb_id"] = result["external_ids"].get("imdb_id")
        result["title"] = result["name"]
        result["release_date"] = result.get("first_air_date")
        result["keywords"] = {"keywords": result["keywords"]["results"]}
        result["runtime"] = None
        return result
