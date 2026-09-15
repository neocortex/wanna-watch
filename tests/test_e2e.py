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
                service_ids=None,
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
    env["WANNA_WATCH_PASSWORD"] = "browser-test-password" if request.node.name == "test_browser_password_login" else ""
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
                if httpx.get(f"{url}/healthz").status_code == 200:
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
        page.get_by_role("button", name="Subscriptions", exact=True).click()
        page.get_by_text("Add TMDB_READ_TOKEN", exact=False).wait_for()
        assert page.locator("#save-services").is_disabled()
        page.get_by_role("button", name="Close subscriptions").click()
        page.keyboard.press("Escape")
        page.get_by_role("navigation", name="Watch status").get_by_role("button", name="Watched", exact=True).click()
        assert (
            page.get_by_role("navigation", name="Watch status")
            .get_by_role("button", name="Watched", exact=True)
            .get_attribute("aria-pressed")
            == "true"
        )
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
        page.get_by_role("navigation", name="Watch status").get_by_role("button", name="Watched", exact=True).click()
        watched = page.locator(f'[data-movie-id="{movie_id}"]')
        watched.wait_for()
        watched.get_by_role("button", name="Restore").click()
        watched.wait_for(state="detached")
        page.get_by_role("button", name="Discover", exact=True).click()
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
@pytest.mark.parametrize("width", [390, 1440])
def test_catalog_filter_panels_and_saved_subscriptions(server: str, width: int) -> None:
    """Apply real service subsets and metadata together, cancel drafts, and reset defaults."""
    with httpx.Client(base_url=server) as client:
        before = client.get("/api/status").json()
    subscriptions = before["preferences"]["provider_ids"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)
        page.locator(".movie-card").first.wait_for()
        expect(page.locator("#open-filters")).to_have_text("Filters")
        expect(page.locator("#reset-filters")).not_to_be_visible()
        expect(page.locator("#open-services, #active-filters")).to_have_count(0)
        subscriptions_button = page.locator("#edit-services").bounding_box()
        refresh_button = page.locator("#refresh").bounding_box()
        assert subscriptions_button["x"] < refresh_button["x"]
        assert abs(subscriptions_button["y"] - refresh_button["y"]) < 3
        page.evaluate("window.scrollTo(0, 1500)")
        scroll = page.evaluate("scrollY")
        assert page.locator("#open-filters").bounding_box()["y"] < 110
        page.locator("#open-filters").click()
        page.locator("#imdb-rating").select_option("6.9")
        # Reason: a real status poll must not overwrite an unsaved draft.
        with page.expect_response(lambda response: response.url.endswith("/api/status")):
            pass
        expect(page.locator("#imdb-rating")).to_have_value("6.9")
        page.keyboard.press("Escape")
        expect(page.locator("#open-filters")).to_be_focused()
        assert abs(page.evaluate("scrollY") - scroll) < 3
        assert page.request.get(server + "/api/status").json()["preferences"] == before["preferences"]
        page.locator("#open-filters").click()
        for provider in subscriptions[1:]:
            page.locator(f'#service-filter-options input[value="{provider}"]').uncheck()
        page.get_by_role("button", name="Apply filters", exact=True).click()
        expect(page.locator("#filters-dialog")).not_to_be_visible()
        saved = page.request.get(server + "/api/status").json()
        assert saved["preferences"]["provider_ids"] == subscriptions
        assert saved["preferences"]["service_ids"] == (subscriptions[:1] if len(subscriptions) > 1 else None)
        assert saved["snapshot"] == before["snapshot"]
        assert saved["needs_refresh"] == before["needs_refresh"]
        assert abs(page.evaluate("scrollY") - scroll) < 3
        page.locator("#open-filters").click()
        page.locator("#language").select_option("en")
        page.locator("#after-year").select_option("1990")
        page.locator("#min-votes").select_option("0")
        expect(page.locator("#imdb-rating option")).to_have_count(41)
        expect(page.locator("#imdb-rating option").first).to_have_text("10.0")
        expect(page.locator("#imdb-rating option").last).to_have_text("6.0")
        page.locator("#imdb-rating").select_option("7.6")
        page.locator('#genre-options input[value="99"]').check()
        page.locator("#exclude-standup").check()
        Path("test-results").mkdir(exist_ok=True)
        page.locator("#filters-dialog").evaluate("dialog => dialog.scrollTop = 0")
        page.screenshot(path=f"test-results/filter-panel-{width}.png")
        page.get_by_role("button", name="Apply filters", exact=True).click()
        expect(page.locator("#filters-dialog")).not_to_be_visible()
        result = page.request.get(server + "/api/movies?limit=80").json()
        assert result["total"] > 0
        expect(page.locator("#count")).to_have_text(f"{result['total']:,} titles")
        assert abs(page.evaluate("scrollY") - scroll) < 3
        for movie in result["movies"]:
            assert movie["original_language"] == "en"
            assert int(movie["year"]) > 1990
            assert movie["imdb_rating"] <= 7.6
            assert not movie["is_standup"]
            assert 99 not in [genre["id"] for genre in movie["genres"]]
            assert {p["provider_id"] for p in movie["providers"]} <= set(subscriptions[:1])
        if result["total"] > 40:
            page.get_by_role("button", name="Show more titles").click()
        expect(page.locator(".movie-card")).to_have_count(len(result["movies"]))
        assert page.locator(".movie-card").evaluate_all("cards => cards.map(c => Number(c.dataset.movieId))") == [
            movie["id"] for movie in result["movies"]
        ]
        page.reload()
        page.locator(".movie-card").first.wait_for()
        page.locator("#open-filters").click()
        expect(page.locator("#imdb-rating")).to_have_value("7.6")
        expect(page.locator("#after-year")).to_have_value("1990")
        before_reset = page.request.get(server + "/api/status").json()["preferences"]
        page.locator("#reset-filters").click()
        expect(page.locator("#min-votes")).to_have_value("5000")
        expect(page.locator("#imdb-rating")).to_have_value("10")
        assert page.request.get(server + "/api/status").json()["preferences"] == before_reset
        page.get_by_role("button", name="Apply filters", exact=True).click()
        expect(page.locator("#filters-dialog")).not_to_be_visible()
        expect(page.locator("#open-filters")).to_have_text("Filters")
        reset = page.request.get(server + "/api/status").json()["preferences"]
        assert reset == {
            **before["preferences"],
            "min_votes": 5000,
            "language": "en",
            "excluded_genres": [16, 99],
            "exclude_standup": True,
        }
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
        page.screenshot(path=f"test-results/filter-bar-{width}.png")
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
        page.get_by_role("navigation", name="Watch status").get_by_role("button", name="Watched", exact=True).click()
        page.locator(selector).wait_for()
        page.reload()
        expect(page.locator("#media-type")).to_have_value("tv")
        page.locator(".movie-card").first.wait_for()
        page.get_by_role("navigation", name="Watch status").get_by_role("button", name="Watched", exact=True).click()
        page.locator(selector).get_by_role("button", name="Restore").click()
        page.locator(selector).wait_for(state="detached")
        page.get_by_role("button", name="Discover", exact=True).click()
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


@pytest.mark.parametrize("width", [320, 390, 700, 850, 1440])
def test_retro_layout_keyboard_and_reduced_motion(server: str, width: int) -> None:
    """Keep retro assets, filters, focus and reduced-motion behavior usable at each width."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900}, reduced_motion="reduce")
        page.goto(server)
        page.locator("#empty:not([hidden])").wait_for()
        page.evaluate("document.fonts.ready")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator("h1").evaluate("el => getComputedStyle(el).animationName") == "none"
        expect(page.locator(".brand-description")).to_contain_text("Less scrolling,")
        expect(page.locator("#refresh-label")).to_have_text("Refresh catalog")
        expect(page.locator("#refresh svg")).to_be_visible()
        assert page.request.get(f"{server}/static/images/video-store.jpg").status == 200
        assert page.evaluate("document.fonts.check('italic 800 64px \"Barlow Condensed\"')")
        assert page.locator("#after-year").evaluate("element => element.tagName") == "SELECT"
        expect(page.locator('#after-year option[value="1990"]')).to_have_count(1)
        page.locator("#open-filters").click()
        for selector in ["#language", "#after-year", "#imdb-rating"]:
            assert page.locator(selector).bounding_box()["width"] >= 120
        page.keyboard.press("Escape")
        page.locator("#edit-services").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#services-dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#services-dialog")).not_to_be_visible()
        expect(page.locator("#edit-services")).to_be_focused()
        Path("test-results").mkdir(exist_ok=True)
        page.locator(".intro").screenshot(path=f"test-results/heading-{width}.png")
        browser.close()


def test_browser_password_login(server: str) -> None:
    """Persist login across browser contexts and clear it on sign out."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto(server)
        page.get_by_label("Password", exact=True).fill("wrong")
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.get_by_role("alert")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_label("Password", exact=True).fill("browser-test-password")
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.get_by_role("heading", name="Tonight, sorted.")).to_be_visible()
        assert context.request.get(f"{server}/api/status").status == 200
        saved = context.storage_state()
        context.close()
        reopened = browser.new_context(storage_state=saved)
        page = reopened.new_page()
        page.goto(server)
        expect(page.get_by_role("heading", name="Tonight, sorted.")).to_be_visible()
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.get_by_label("Password", exact=True)).to_be_visible()
        assert reopened.request.get(f"{server}/api/status").status == 401
        browser.close()
