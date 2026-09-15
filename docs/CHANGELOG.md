# Changelog

## Unreleased

- Render cached audio warnings with the initial cards and prefetch checks near the viewport.

- Add optional provider-level “English may be unavailable” labels using cached
  Streaming Availability API subscription audio data for English-original titles.

- Add a pink-and-cyan W favicon on navy to the catalog and sign-in pages.

- Anchor the diagonal heading underline below the punctuation and space it clear of the refresh action on all screens.
- Deepen the neon video-store interface with layered navy gradients, a structured responsive filter console,
  polished poster sleeves, and restrained storefront, heading, refresh, and hover motion.
- Replace the storefront marquee copy with fictional text-free poster artwork, change the masthead line to
  “Less scrolling, more watching,” and make Released after a complete year dropdown.
- Give the live-text title a split-tone highlight, rim light and stepped extrusion, and make the wordmark more
  dynamic with independently angled words, layered shadows and three cyan speed lines.

- Replace the browser password prompt with a mobile-friendly login page and 30-day
  sessions, with sign out and automatic revocation when the shared password changes.

- Protect hosted access with a shared password, reject cross-site writes, require
  credentials on Railway, and expose a minimal public healthcheck.

- Add a production Docker image and Railway setup instructions with persistent
  storage and a build context that excludes credentials and personal data.

- Redesign the catalog as an 80s neon video store with pink/cyan lettering,
  generated storefront artwork, self-hosted Barlow fonts, and framed real posters.
- Compact the subscription and filter layout across desktop and mobile, preserve
  the refresh icon during status updates, and add keyboard/reduced-motion checks.

- Consolidate project documentation under docs/ and expand generated-file ignore rules.

- Change rating filtering to an inclusive maximum, preserving lower-rated results.
- Default/reset to English with Animation, Documentary, and Stand-up excluded.
- Present stand-up with genres, simplify filter copy, and link posters to IMDb.

- Replace the media-type dropdown with Films and Series tabs; remove the combined
  browser list and keep ratings and pagination separate for each type.

- Add separate Films and Series lists with whole-series IMDb ratings, premiere-year
  filtering, season counts, and typed watch-provider links.
- Collect movie and TV catalogs together and preserve film history while migrating
  IDs and watched/hidden records to separate movie/series identities.

- Apply filters automatically: selections immediately, numeric entries after a
  350 ms pause. Remove the Apply button and preserve rapid edits during requests.

- Add a saved maximum IMDb rating filter (1.0–10.0 in 0.1 steps), combined with
  existing filters before pagination; blank and Reset filters restore any rating.

- Show TMDB genres and original language on film cards.
- Add saved genre exclusions, stand-up exclusion, original-language
  choices, and an exclusive release-year lower bound with automatic updates and Reset controls.
- Apply combined filters before pagination in every watch-state view; retain
  them when changing subscriptions or minimum votes.
- Extend database, API, mobile-browser, and live metadata verification.

## 0.1.0 — 2026-09-13

- Add a personal, phone-friendly browser for German subscription films.
- Collect complete TMDB discovery results and validate exact subscription offers.
- Join official IMDb ratings by ID and rank before paginating.
- Persist subscription preferences and watched/hidden history in SQLite.
- Add atomic catalog refreshes, freshness and coverage reporting, and a live audit.
- Add unit, real-database integration, and Chromium end-to-end tests.
- Validate the live six-service catalog, all eligible IMDb scores, and top-ten
  German subscription offers; pass all 29 tests.
