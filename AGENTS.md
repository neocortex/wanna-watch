# Project guidance

Follow the user's Python development guidance: KISS, surgical edits, type hints,
Google-style docstrings, 119-character Python lines, and modules under 500 lines.

## Architecture

- Use `uv` exclusively; add/remove dependencies with `uv add` / `uv remove`.
- Backend: Python 3.12+, FastAPI, httpx, SQLite, and python-dotenv.
- Frontend: plain HTML/CSS/JavaScript served by FastAPI. No frontend bundler.
- One personal server process. Preferences and history live in SQLite.
- Railway uses a persistent /data volume, one replica, and no service sleeping.
- WANNA_WATCH_PASSWORD is required on Railway; only GET /healthz bypasses authentication.
- `TMDB_READ_TOKEN` is a server-only credential. Never expose or commit `.env`.
- Catalogs must come from real TMDB/JustWatch and IMDb data. Do not seed demos.
- IMDb ratings and IMDb votes must never be replaced with TMDB's rating fields.
- Rank the full catalog before UI pagination. Do not impose a top-N upstream cutoff.
- Preserve a usable catalog on refresh failure. Publish snapshots atomically.
- Keep personal watched/hidden history independent of catalog availability.
- Identify titles by (media_type, TMDB ID); film and series numeric IDs can overlap.
- Collect and publish movie and TV catalogs together. TV ratings and history refer
  to the whole show; use external_ids.imdb_id and first_air_date for series.
- Apply genre, original-language, exclusive release-year, and maximum IMDb rating filters before pagination.
- Stand-up uses TMDB keyword 9716 internally; show it alongside genres in the UI.
  Do not infer it from titles or exclude all Comedy.
- Original language is film metadata, not provider dubbing or subtitle availability.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run playwright install chromium
uv run pytest
uv run python -m wanna_watch.verify --limit 10
```

The live audit needs a real refreshed catalog and a TMDB token. Populated E2E
tests use a copy of the real catalog and explicitly skip when none exists. Do not
claim live verification based on offline tests. Pure function boundary inputs
belong only in tests; do not introduce mocked API implementations.

Keep [README.md](README.md), the guides in [docs/](docs/), and
[docs/CHANGELOG.md](docs/CHANGELOG.md) current when changing behavior, setup, or scope.
Keep README.md and AGENTS.md at the root; place other project documentation in docs/.
Never use `--no-verify` when committing. Do not add a Codex co-author.

## Frontend assets

- Self-host display/body fonts under `src/wanna_watch/static/fonts/` with their license.
- Keep decorative artwork separate from real catalog posters and metadata. Store
  generated artwork provenance with the image and in `.impeccable/build/`.
- Preserve keyboard focus and `prefers-reduced-motion` behavior when changing UI motion.
