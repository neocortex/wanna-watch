"""Verify audio labels in Chromium using a real catalog title and cached live evidence."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from wanna_watch.storage import Store


@pytest.mark.e2e
@pytest.mark.parametrize("width", [390, 1440])
def test_audio_label_from_live_cache(tmp_path: Path, width: int) -> None:
    """Show a provider warning at phone and desktop widths from actual cached evidence."""
    source_path = Path(os.getenv("WANNA_WATCH_DATA_DIR", "data")) / "wanna-watch.sqlite3"
    if not source_path.exists():
        pytest.skip("A real catalog with a cached audio warning is required.")
    source = Store(source_path)
    with source.connect() as db:
        rows = db.execute("SELECT key, value FROM settings WHERE key LIKE 'audio:de:%'").fetchall()
    chosen = None
    for key, value in rows:
        cache = json.loads(value)
        media_type, ident = key.removeprefix("audio:de:").split("/")
        movie = source.title(media_type, int(ident))
        if movie and movie.get("original_language") == "en" and cache["services"]:
            if time.time() - cache["checked_at"] < 86400:
                chosen = (key, cache, movie)
                break
    if chosen is None:
        pytest.skip("Fetch a real subscription audio warning before testing its browser label.")
    key, cache, movie = chosen
    store = Store(tmp_path / "wanna-watch.sqlite3")
    store.publish([movie], source.get("snapshot"))
    store.set(key, cache)
    store.set("audio:retry_after", time.time() + 3600)
    store.set(
        "preferences",
        {
            "provider_ids": [p["provider_id"] for p in movie["providers"]],
            "min_votes": 0,
            "excluded_genres": [],
            "exclude_standup": False,
            "language": "en",
            "media_type": movie["media_type"],
        },
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Reason: use real cached evidence without spending quota or allowing outbound calls in E2E.
    env = {
        **os.environ,
        "WANNA_WATCH_DATA_DIR": str(tmp_path),
        "WANNA_WATCH_PASSWORD": "",
        "TMDB_READ_TOKEN": "",
        "STREAMING_AVAILABILITY_API_KEY": "cached-evidence-only",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "wanna_watch.app:create_app", "--factory", "--port", str(port)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{url}/healthz").status_code == 200:
                    break
            except httpx.RequestError:
                time.sleep(0.05)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
            audio_requests = []
            page.on(
                "request",
                lambda request: audio_requests.append(request.url) if request.url.endswith("/audio") else None,
            )
            page.goto(url)
            card = page.locator(".movie-card")
            card.scroll_into_view_if_needed()
            label = card.locator(".audio-warning")
            expect(label).to_have_text("English may be unavailable")
            expect(label).to_be_visible()
            assert audio_requests == []
            assert label.locator("..").get_attribute("data-provider-id") in {"8", "9", "337"}
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            Path("test-results").mkdir(exist_ok=True)
            card.screenshot(path=f"test-results/audio-card-{width}.png")
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
