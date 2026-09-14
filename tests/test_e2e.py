"""Drive Chromium against a real app server; populated tests require a real catalog."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.e2e


@pytest.fixture
def server(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[str]:
    """Run the real web app on an ephemeral port with isolated personal storage."""
    if getattr(request, "param", "empty") == "catalog":
        source_path = Path(os.getenv("WANNA_WATCH_DATA_DIR", "data")) / "wanna-watch.sqlite3"
        if not source_path.exists():
            pytest.skip("A real refreshed catalog is required for populated browser testing.")
        with sqlite3.connect(source_path) as source, sqlite3.connect(tmp_path / "wanna-watch.sqlite3") as target:
            if not source.execute("SELECT 1 FROM movies LIMIT 1").fetchone():
                pytest.skip("No real films collected yet; the browser will not use fabricated availability.")
            source.backup(target)
        with sqlite3.connect(tmp_path / "wanna-watch.sqlite3") as target:
            target.execute("DELETE FROM history")
            # Reason: browser scenarios start consistently without changing the personal database.
            prefs = json.loads(target.execute("SELECT value FROM settings WHERE key='preferences'").fetchone()[0])
            prefs.update(
                media_type="movie",
                min_votes=5000,
                excluded_genres=[],
                exclude_standup=False,
                language="all",
                after_year=None,
                imdb_rating=None,
            )
            target.execute("UPDATE settings SET value=? WHERE key='preferences'", (json.dumps(prefs),))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "WANNA_WATCH_DATA_DIR": str(tmp_path), "TMDB_READ_TOKEN": ""}
    # Reason: an isolated working directory prevents accidental reads of personal .env credentials.
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
            if process.poll() is not None:
                pytest.fail("Browser-test server exited before startup.")
            try:
                if httpx.get(f"{url}/api/status").status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("Browser-test server did not become ready.")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_mobile_setup_without_credentials(server: str) -> None:
    """Verify a usable empty state and actionable setup with no invented films."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)
        page.locator("#empty:not([hidden])").wait_for()
        assert page.get_by_role("heading", name="Tonight, sorted.").is_visible()
        assert page.locator("#refresh").is_disabled()
        assert page.locator(".movie-card").count() == 0
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.get_by_role("button", name="Choose services").click()
        page.get_by_text("Add TMDB_READ_TOKEN", exact=False).wait_for()
        assert page.locator("#save-services").is_disabled()
        page.get_by_role("button", name="Close subscriptions").click()
        page.get_by_role("button", name="Watched", exact=True).click()
        assert page.get_by_role("button", name="Watched", exact=True).get_attribute("aria-pressed") == "true"
        assert errors == []
        Path("test-results").mkdir(exist_ok=True)
        page.screenshot(path="test-results/mobile-setup.png", full_page=True)
        browser.close()


@pytest.mark.live
@pytest.mark.parametrize("server", ["catalog"], indirect=True)
def test_real_catalog_watch_hide_undo_and_reload(server: str) -> None:
    """Exercise film actions in Chromium using a copy of the actual collected catalog."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)
        first = page.locator(".movie-card").first
        first.wait_for()
        movie_id = first.get_attribute("data-movie-id")
        first.get_by_role("button", name="Watched").click()
        page.locator(f'[data-movie-id="{movie_id}"]').wait_for(state="detached")
        page.reload()
        page.locator(".movie-card").first.wait_for()
        page.get_by_role("button", name="Watched", exact=True).click()
        watched = page.locator(f'[data-movie-id="{movie_id}"]')
        watched.wait_for()
        watched.get_by_role("button", name="Restore").click()
        watched.wait_for(state="detached")
        page.get_by_role("button", name="To discover", exact=True).click()
        restored = page.locator(f'[data-movie-id="{movie_id}"]')
        restored.wait_for()
        restored.get_by_role("button", name="Hide", exact=True).click()
        restored.wait_for(state="detached")
        page.get_by_role("button", name="Undo", exact=True).click()
        restored.wait_for()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert errors == []
        Path("test-results").mkdir(exist_ok=True)
        page.screenshot(path="test-results/mobile-catalog.png", full_page=True)
        browser.close()


@pytest.mark.live
@pytest.mark.parametrize("server", ["catalog"], indirect=True)
def test_real_catalog_service_filters_and_pagination(server: str) -> None:
    """Save service and vote filters in the browser, then verify paginated ordering."""
    with httpx.Client(base_url=server) as client:
        selected = client.get("/api/status").json()["preferences"]["provider_ids"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        page.goto(server)
        page.locator(".movie-card").first.wait_for()
        page.get_by_role("button", name="Choose services").click()
        page.locator("#provider-options input").first.wait_for()
        for provider_id in selected[1:]:
            page.locator(f'#provider-options input[value="{provider_id}"]').uncheck()
        page.get_by_role("button", name="Save subscriptions").click()
        expect(page.locator("#services-dialog")).not_to_be_visible()
        expect(page.locator("#selected-services .chip")).to_have_count(1)
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.locator("#min-votes").select_option("0")
        with httpx.Client(base_url=server) as client:
            expected = client.get("/api/movies?limit=80").json()
            assert client.get("/api/status").json()["preferences"] == {
                "provider_ids": selected[:1],
                "media_type": "movie",
                "min_votes": 0,
                "excluded_genres": [],
                "exclude_standup": False,
                "language": "all",
                "after_year": None,
                "imdb_rating": None,
            }
        expect(page.locator("#count")).to_have_text(f"{expected['total']:,} titles")
        if expected["total"] > 40:
            page.get_by_role("button", name="Show more titles").click()
        expect(page.locator(".movie-card")).to_have_count(len(expected["movies"]))
        actual_ids = page.locator(".movie-card").evaluate_all(
            "cards => cards.map(card => Number(card.dataset.movieId))"
        )
        assert actual_ids == [movie["id"] for movie in expected["movies"]]
        page.reload()
        page.locator(".movie-card").first.wait_for()
        expect(page.locator("#min-votes")).to_have_value("0")
        expect(page.locator("#selected-services .chip")).to_have_count(1)
        browser.close()


@pytest.mark.live
@pytest.mark.parametrize("server", ["catalog"], indirect=True)
def test_real_catalog_genre_language_year_filters(server: str) -> None:
    """Filter real metadata on mobile, preserve filters across edits, and reset them."""
    with httpx.Client(base_url=server) as client:
        prefs = client.get("/api/status").json()["preferences"]
        baseline = client.get("/api/movies?limit=100").json()["total"]
        assert client.get("/api/status").json()["genres"], "Enrich the real catalog before testing genre controls."
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)
        page.locator(".movie-card").first.wait_for()
        assert page.locator("#language").bounding_box()["width"] >= 120
        assert page.locator("#after-year").bounding_box()["width"] >= 120
        page.locator("#genre-summary").click()
        page.locator('#genre-options input[value="99"]').check()
        page.locator('#genre-options input[value="16"]').check()
        page.locator("#exclude-standup").check()
        page.locator("#language").select_option("en")
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.locator("#after-year").fill("1990")
        page.wait_for_function("pendingPreferences === 0 && !filterTimer && !filtersDirty && !loading")
        expect(page.locator("#after-year")).to_have_value("1990")
        with httpx.Client(base_url=server) as client:
            expected = client.get("/api/movies?limit=80").json()
            saved = client.get("/api/status").json()["preferences"]
        assert 0 < expected["total"] < baseline
        assert saved == {
            **prefs,
            "excluded_genres": [16, 99],
            "exclude_standup": True,
            "language": "en",
            "after_year": 1990,
        }
        for movie in expected["movies"]:
            assert movie["original_language"] == "en"
            assert int(movie["year"]) > 1990
            assert not {16, 99}.intersection(g["id"] for g in movie["genres"])
            assert movie["is_standup"] is False
        expect(page.locator("#count")).to_have_text(f"{expected['total']:,} titles")
        if expected["total"] > 40:
            page.get_by_role("button", name="Show more titles").click()
        expect(page.locator(".movie-card")).to_have_count(len(expected["movies"]))
        assert page.locator(".movie-card").evaluate_all("cards => cards.map(c => Number(c.dataset.movieId))") == [
            m["id"] for m in expected["movies"]
        ]
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.locator("#min-votes").select_option("0")
        page.reload()
        page.locator(".movie-card").first.wait_for()
        expect(page.locator("#language")).to_have_value("en")
        expect(page.locator("#after-year")).to_have_value("1990")
        expect(page.locator("#exclude-standup")).to_be_checked()
        expect(page.locator('#genre-options input[value="99"]')).to_be_checked()
        expect(page.locator(".movie-language").first).to_have_text("English")
        page.get_by_role("button", name="Choose services").click()
        page.locator("#provider-options input").first.wait_for()
        for provider_id in prefs["provider_ids"][1:]:
            page.locator(f'#provider-options input[value="{provider_id}"]').uncheck()
        page.get_by_role("button", name="Save subscriptions").click()
        expect(page.locator("#services-dialog")).not_to_be_visible()
        prefs["provider_ids"] = prefs["provider_ids"][:1]
        with httpx.Client(base_url=server) as client:
            assert client.get("/api/status").json()["preferences"] == {
                **saved,
                "provider_ids": prefs["provider_ids"],
                "min_votes": 0,
            }
        expect(page.locator("#language")).to_have_value("en")
        expect(page.locator("#after-year")).to_have_value("1990")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        Path("test-results").mkdir(exist_ok=True)
        page.screenshot(path="test-results/mobile-filters.png", full_page=True)
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.get_by_role("button", name="Reset filters", exact=True).click()
        expect(page.locator("#after-year")).to_have_value("")
        expect(page.locator("#language")).to_have_value("en")
        with httpx.Client(base_url=server) as client:
            reset = client.get("/api/status").json()["preferences"]
        assert reset == {
            **prefs,
            "min_votes": 0,
            "language": "en",
            "excluded_genres": [16, 99],
            "exclude_standup": True,
        }
        assert errors == []
        browser.close()


@pytest.mark.live
@pytest.mark.parametrize("server", ["catalog"], indirect=True)
def test_real_catalog_maximum_rating_and_reset(server: str) -> None:
    """Use a decimal rating on mobile and preserve it across reloads and vote changes."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        page.goto(server)
        page.locator(".movie-card").first.wait_for()
        assert page.locator("#imdb-rating").bounding_box()["width"] >= 120
        for rating in ["7.6", "6.9"]:
            with page.expect_response(lambda response: "/api/movies?" in response.url):
                page.locator("#imdb-rating").fill(rating)
            with httpx.Client(base_url=server) as client:
                result = client.get("/api/movies?limit=100").json()
            assert result["total"] > 0
            assert all(movie["imdb_rating"] <= float(rating) for movie in result["movies"])
            poster = page.locator("a.poster-wrap").first
            expect(poster).to_have_attribute("href", f"https://www.imdb.com/title/{result['movies'][0]['imdb_id']}/")
            expect(poster).to_have_attribute("target", "_blank")
            assert page.locator("#genre-options #exclude-standup").count() == 1
            assert page.locator(".filter-help, .filter-label").count() == 0
            assert "TMDB keyword" not in page.locator("#filters-form").inner_text()
            expect(page.locator("#count")).to_have_text(f"{result['total']:,} titles")
            expect(page.locator(".rating").first).to_have_text(f"★ {rating}")
        page.reload()
        page.locator(".movie-card").first.wait_for()
        expect(page.locator("#imdb-rating")).to_have_value("6.9")
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.locator("#min-votes").select_option("0")
        expect(page.locator("#imdb-rating")).to_have_value("6.9")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path="test-results/mobile-rating-filter.png")
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.get_by_role("button", name="Reset filters", exact=True).click()
        expect(page.locator("#imdb-rating")).to_have_value("")
        with httpx.Client(base_url=server) as client:
            assert client.get("/api/status").json()["preferences"]["imdb_rating"] is None
        browser.close()


@pytest.mark.live
@pytest.mark.parametrize("server", ["catalog"], indirect=True)
def test_automatic_filters_keep_latest_edit_on_slow_network(server: str) -> None:
    """Keep typing and rapid selections usable while real HTTP responses are delayed."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)
        page.locator(".movie-card").first.wait_for()
        expect(page.get_by_role("button", name="Apply filters", exact=True)).to_have_count(0)
        session = page.context.new_cdp_session(page)
        session.send("Network.enable")
        session.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 180,
                "downloadThroughput": -1,
                "uploadThroughput": -1,
            },
        )
        rating = page.locator("#imdb-rating")
        with page.expect_request(lambda request: request.url.endswith("/api/preferences") and request.method == "PUT"):
            rating.fill("7.6")
        expect(rating).to_be_enabled()
        rating.fill("6.9")
        page.locator("#language").select_option("de")
        page.locator("#language").select_option("en")
        page.locator("#after-year").fill("2000")
        page.wait_for_function("pendingPreferences === 0 && !filterTimer && !filtersDirty && !loading")
        expect(rating).to_have_value("6.9")
        expect(page.locator("#language")).to_have_value("en")
        expect(page.locator("#after-year")).to_have_value("2000")
        with httpx.Client(base_url=server) as client:
            prefs = client.get("/api/status").json()["preferences"]
            result = client.get("/api/movies").json()
        assert prefs["imdb_rating"] == 6.9
        assert prefs["language"] == "en"
        assert prefs["after_year"] == 2000
        expect(page.locator("#count")).to_have_text(f"{result['total']:,} titles")
        assert result["total"] > 0
        assert page.locator(".movie-card").evaluate_all("cards => cards.map(c => Number(c.dataset.movieId))") == [
            movie["id"] for movie in result["movies"]
        ]
        # Reason: invalid partial edits must survive status polling without being sent as valid preferences.
        rating.fill("7.65")
        with page.expect_response(lambda response: response.url.endswith("/api/status")):
            pass
        expect(rating).to_have_value("7.65")
        with httpx.Client(base_url=server) as client:
            assert client.get("/api/status").json()["preferences"]["imdb_rating"] == 6.9
        rating.fill("7.6")
        page.get_by_role("button", name="Reset filters", exact=True).click()
        page.wait_for_function("pendingPreferences === 0 && !filterTimer && !filtersDirty && !loading")
        expect(rating).to_have_value("")
        with httpx.Client(base_url=server) as client:
            prefs = client.get("/api/status").json()["preferences"]
        assert prefs["imdb_rating"] is None
        assert prefs["language"] == "en"
        assert prefs["after_year"] is None
        assert errors == []
        browser.close()


@pytest.mark.live
@pytest.mark.parametrize("server", ["catalog"], indirect=True)
def test_separate_film_and_series_lists(server: str) -> None:
    """Keep films and series in separate mobile lists with persistent typed history."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)
        page.locator(".movie-card").first.wait_for()
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.get_by_role("button", name="Series", exact=True).click()
        first = page.locator('.movie-card[data-media-type="tv"]').first
        first.wait_for()
        expect(page.locator('.movie-card[data-media-type="movie"]')).to_have_count(0)
        expect(first.locator(".movie-meta")).to_contain_text("Series")
        assert "/tv/" in first.locator(".where-link").get_attribute("href")
        movie_id = first.get_attribute("data-movie-id")
        selector = f'.movie-card[data-media-type="tv"][data-movie-id="{movie_id}"]'
        first.get_by_role("button", name="Watched").click()
        page.locator(selector).wait_for(state="detached")
        page.get_by_role("button", name="Watched", exact=True).click()
        page.locator(selector).wait_for()
        page.reload()
        expect(page.locator("#media-type")).to_have_value("tv")
        page.locator(".movie-card").first.wait_for()
        page.get_by_role("button", name="Watched", exact=True).click()
        page.locator(selector).get_by_role("button", name="Restore").click()
        page.locator(selector).wait_for(state="detached")
        page.get_by_role("button", name="To discover", exact=True).click()
        page.locator(selector).get_by_role("button", name="Hide", exact=True).click()
        page.locator(selector).wait_for(state="detached")
        page.get_by_role("button", name="Undo", exact=True).click()
        page.locator(selector).wait_for()
        with page.expect_response(lambda response: "/api/movies?" in response.url):
            page.get_by_role("button", name="Films", exact=True).click()
        with httpx.Client(base_url=server) as client:
            expected = client.get("/api/movies?limit=80").json()
        expect(page.locator("#count")).to_have_text(f"{expected['total']:,} titles")
        if expected["total"] > 40:
            page.get_by_role("button", name="Show more titles").click()
        expect(page.locator(".movie-card")).to_have_count(len(expected["movies"]))
        assert page.locator(".movie-card").evaluate_all(
            "cards => cards.map(c => [c.dataset.mediaType, Number(c.dataset.movieId)])"
        ) == [[m["media_type"], m["id"]] for m in expected["movies"]]
        assert {m["media_type"] for m in expected["movies"]} == {"movie"}
        expect(page.locator('.movie-card[data-media-type="tv"]')).to_have_count(0)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
        page.screenshot(path="test-results/mobile-series.png")
        browser.close()
