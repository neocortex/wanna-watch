"""Serve the single-user film and series browser and manage background catalog refreshes."""

import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wanna_watch.catalog import refresh_catalog
from wanna_watch.storage import Store
from wanna_watch.tmdb import TMDB, SourceError

STATIC = Path(__file__).parent / "static"
DEFAULT_GENRES = [{"id": 16, "name": "Animation"}, {"id": 99, "name": "Documentary"}]


def read_token() -> str:
    """Read the token at request time so local credential setup needs no restart.

    Returns:
        The environment token or the project .env token, never sent to browsers.
    """
    return (os.getenv("TMDB_READ_TOKEN") or dotenv_values(".env").get("TMDB_READ_TOKEN") or "").strip()


class Preferences(BaseModel):
    """Validate the selected subscriptions and IMDb vote threshold."""

    provider_ids: list[int] = Field(max_length=30)
    media_type: Literal["movie", "tv"] = "movie"
    min_votes: int = Field(default=5000, ge=0, le=10_000_000)
    excluded_genres: list[int] = Field(
        default_factory=lambda: [genre["id"] for genre in DEFAULT_GENRES], max_length=30
    )
    exclude_standup: bool = True
    language: Literal["all", "en", "de", "fr", "other"] = "en"
    after_year: int | None = Field(default=None, ge=0, le=9999)
    imdb_rating: float | None = Field(default=None, ge=1, le=10, multiple_of=0.1)


class WatchState(BaseModel):
    """Validate a title's personal watch state."""

    state: Literal["unseen", "watched", "hidden"]


def create_app(data_dir: Path | None = None) -> FastAPI:
    """Create the application with a private persistent data directory.

    Args:
        data_dir: Optional explicit directory, also used for isolated real-database tests.

    Returns:
        Configured FastAPI application.
    """
    directory = data_dir or Path(os.getenv("WANNA_WATCH_DATA_DIR", "data"))
    store = Store(directory / "wanna-watch.sqlite3")
    saved = store.get("preferences", {})
    if saved.get("media_type") == "all":
        store.set("preferences", {**saved, "media_type": "movie"})
    lock = threading.Lock()
    status = {"running": False, "message": "", "error": None}
    worker: threading.Thread | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Let an active refresh finish during a graceful server shutdown."""
        yield
        if worker is not None:
            worker.join()

    app = FastAPI(title="Wanna Watch", lifespan=lifespan)
    app.state.store = store
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        """Return the mobile-friendly film browser."""
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    def get_status() -> dict:
        """Report refresh progress, catalog coverage, and saved preferences."""
        snapshot = store.get("snapshot")
        preferences = Preferences(**store.get("preferences", {"provider_ids": []})).model_dump()
        stale = (
            snapshot is None
            or (datetime.now(UTC) - datetime.fromisoformat(snapshot["started_at"])).total_seconds() > 86400
        )
        covered = set(snapshot["provider_ids"]) if snapshot else set()
        with lock:
            current = dict(status)
        return {
            **current,
            "configured": bool(read_token()),
            "snapshot": snapshot,
            "preferences": preferences,
            "genres": store.get("genres", DEFAULT_GENRES),
            "stale": stale,
            "needs_refresh": stale
            or not set(preferences["provider_ids"]).issubset(covered)
            or (preferences["media_type"] != "movie" and "tv" not in (snapshot or {}).get("media_types", [])),
        }

    @app.get("/api/providers")
    def providers() -> dict:
        """Load and cache the combined German film and series provider directory."""
        cached = store.get("providers", [])
        today = datetime.now(UTC).date().isoformat()
        if cached and store.get("providers_date") == today:
            return {"providers": cached}
        try:
            source = TMDB(read_token())
            try:
                available = source.providers()
                store.set("providers", available)
                store.set("providers_date", today)
                return {"providers": available}
            finally:
                source.close()
        except SourceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None

    @app.put("/api/preferences")
    def preferences(body: Preferences) -> dict:
        """Save validated subscriptions and vote threshold for this personal app."""
        known = {p["provider_id"] for p in store.get("providers", [])}
        if not set(body.provider_ids).issubset(known):
            raise HTTPException(422, "Choose subscriptions from the German provider list.")
        known_genres = {16, 99} | {g["id"] for g in store.get("genres", [])}
        if not set(body.excluded_genres).issubset(known_genres):
            raise HTTPException(422, "Choose genres from the TMDB genre list.")
        with lock:
            if status["running"]:
                raise HTTPException(409, "Wait for the catalog refresh to finish before changing filters.")
            value = body.model_dump()
            value["provider_ids"] = sorted(set(body.provider_ids))
            value["excluded_genres"] = sorted(set(body.excluded_genres))
            store.set("preferences", value)
        return value

    @app.get("/api/movies")
    def movies(
        view: Literal["unseen", "watched", "hidden"] = "unseen",
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=40, ge=1, le=100),
    ) -> dict:
        """Paginate only after filtering and IMDb sorting the complete stored catalog."""
        prefs = Preferences(**store.get("preferences", {"provider_ids": []})).model_dump()
        result = store.movies(providers=prefs.pop("provider_ids"), view=view, **prefs)
        return {"movies": result[offset : offset + limit], "total": len(result)}

    @app.put("/api/movies/{movie_id}/state")
    def state(movie_id: int, body: WatchState) -> dict:
        """Persist watched, hidden, or unseen state independently of catalog refreshes."""
        try:
            store.set_state(movie_id, body.state)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None
        return {"id": movie_id, "state": body.state}

    @app.put("/api/titles/{media_type}/{movie_id}/state")
    def title_state(media_type: Literal["movie", "tv"], movie_id: int, body: WatchState) -> dict:
        """Keep whole-series history separate from films with the same TMDB ID."""
        try:
            store.set_state(movie_id, body.state, media_type)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None
        return {"id": movie_id, "media_type": media_type, "state": body.state}

    def progress(message: str) -> None:
        """Update the current background refresh message under the status lock."""
        with lock:
            status["message"] = message

    def run_refresh(source: TMDB, selected: list[int]) -> None:
        """Publish a complete catalog or preserve the prior snapshot on failure."""
        try:
            refresh_catalog(source, store, directory, selected, progress)
        except (SourceError, ValueError) as exc:
            with lock:
                status["error"] = str(exc)
        except (httpx.HTTPError, OSError):
            with lock:
                status["error"] = "The dataset could not be downloaded or saved. Your previous catalog is unchanged."
        except Exception:
            with lock:
                status["error"] = (
                    "Unexpected catalog response. No partial catalog was published. Try refreshing again."
                )
        finally:
            source.close()
            with lock:
                status["running"] = False

    @app.post("/api/refresh", status_code=202)
    def refresh() -> dict:
        """Start one refresh, keeping the current catalog available during collection."""
        nonlocal worker
        with lock:
            if status["running"]:
                raise HTTPException(409, "A refresh is already running.")
            selected = store.get("preferences", {}).get("provider_ids", [])
            if not selected:
                raise HTTPException(422, "Choose at least one subscription first.")
            try:
                source = TMDB(read_token())
            except SourceError as exc:
                raise HTTPException(503, str(exc)) from None
            status.update(running=True, message="Starting catalog refresh…", error=None)
            worker = threading.Thread(target=run_refresh, args=(source, selected), daemon=True)
            worker.start()
        return {"message": "Refresh started."}

    return app
