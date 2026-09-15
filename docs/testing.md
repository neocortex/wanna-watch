# Testing and verification

Run from the project root after `uv sync`:

```bash
uv run ruff check .
uv run ruff format --check .
node --check src/wanna_watch/static/app.js
node --check src/wanna_watch/static/audio.js
uv run playwright install chromium
uv run pytest
```

The JavaScript syntax check requires Node.js; the application itself does not.

Tests cover IMDb parsing, subscription-offer boundaries, real SQLite migration and
rollback, filtering before pagination, saved preferences, and typed film/series
history. Chromium exercises setup, separate lists, actions, filters, poster links,
and rapid edits over a delayed network.

Unit boundary inputs are isolated test data. No mock upstream API or production
demo catalog is used. Populated browser tests copy the actual saved catalog and
reset only the copy's preferences/history. The personal database stays untouched.
Screenshots are generated in the ignored `test-results/` directory.

Audio unit tests cover unknown data, multiple editions, and subscription-only
matching. HTTP tests exercise a real SQLite cache and typed title identities.
`tests/test_audio_e2e.py` requires a real English-original catalog title with a
fresh cached warning: browse such a title with the optional audio key configured
first. It uses that actual evidence in an isolated store, blocks new upstream
lookups, and checks the provider label at phone and desktop widths. It skips if
no suitable evidence is available; it does not fabricate audio offers.

Tests requiring a saved catalog, IMDb download, or TMDB credential skip when those
inputs are missing. For a complete run without skips, configure `.env` and finish
a real catalog refresh first. Live tests contact the real services; one also
refreshes the smallest configured provider into an isolated database.

## Live audit

```bash
uv run python -m wanna_watch.verify --limit 10
uv run pytest -m live
```

The audit checks every eligible rating and vote count against the official IMDb
dataset, independently checks ordering and coverage, and re-fetches up to ten
titles of each selected media type. It validates identities, German subscription
offers, genres, original language, and stand-up tags.

It writes `data/verification.json` and exits unsuccessfully on mismatches. These
are source checks, not proof of playback or entitlement in a streaming account.
Run a refresh if upstream data has changed, then repeat the audit.

For test coverage:

```bash
uv run pytest --cov=src/wanna_watch --cov-report=term-missing
```

Generated test reports and caches are ignored and can be deleted. Historical
session-by-session verification logs are not maintained as project documentation;
use test output and the timestamped JSON audit for current evidence.

The retro-interface E2E checks cover 320, 390, and 1440 pixel viewports,
locally served artwork/fonts, reduced-motion behavior, and subscription-dialog
keyboard focus restoration. Populated interaction tests continue to use a copy
of the actual catalog.
