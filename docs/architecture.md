# Architecture

Wanna Watch is a single-user FastAPI app with a plain HTML/CSS/JavaScript frontend
and SQLite storage. Films and whole TV series have separate browser lists.
Railway hosting uses one process and a persistent volume. Optional password
authentication protects all routes except `/healthz`; Railway requires a password.
Episode tracking, separate user accounts, and native iOS packaging are not implemented.

## Catalog collection

1. Query TMDB's German provider directories for films and series.
2. Collect every discovery page for each selected provider and media type using
   subscription (`flatrate`) offers. Rental and purchase offers are excluded.
3. Partition oversized discovery results by TMDB vote count to stay within the
   500-page API limit. These partitions do not impose a rating cutoff.
4. Deduplicate by `(media_type, TMDB ID)`. Fetch each title's metadata and actual
   German subscription offers. Series use `external_ids.imdb_id` and `first_air_date`.
5. Join exact IMDb IDs to the official `title.ratings.tsv.gz` dataset. Never
   substitute TMDB ratings or fuzzy-match names. Count titles missing ratings or offers.
6. Atomically publish both catalogs, coverage metadata, and the combined genre
   directory. A failed collection leaves the previous snapshot usable.

The IMDb download is reused within the same UTC day. Refreshes run on request in
one background thread; snapshots older than 24 hours are flagged. Full refreshes
can take tens of minutes because every discovered title is checked.

## Browsing and persistence

Filter by selected providers, media type, watch state, IMDb votes, excluded genres,
original language, release year, and maximum IMDb rating. Sort the full eligible
list by rating descending, votes descending, case-insensitive title, media type,
and ID before pagination.

Stand-up uses TMDB keyword 9716 internally and appears alongside genres in the UI.
Original language describes the title, not streaming-service audio tracks.

Optional `audio.py` lookups supplement visible English-original cards through
`GET /api/titles/{media_type}/{movie_id}/audio`. Exact Netflix (8), Prime Video (9),
and Disney+ (337) base subscriptions map to the external API's service IDs.
Rental, purchase, add-on, other-country, and unknown audio data cannot cause warnings.
Every matching subscription edition must report audio and omit English to label a provider.
Show-level series information is advisory; it does not guarantee uniform episode audio.
Title identity is checked against both IMDb and typed TMDB IDs.

Fresh cached labels are included in `/api/movies` without waiting behind upstream
requests. Uncached checks start within 400 pixels of the viewport.
SQLite settings cache results by country and typed title identity for 24 hours,
independently of snapshot publication. Requests are serialized and paced; failures
pause upstream requests for one hour. Expired warnings are not served on failure.
The optional `STREAMING_AVAILABILITY_API_KEY` stays server-side. Audio information
never changes inclusion, ranking, pagination, or TMDB provider availability.

SQLite stores JSON settings and catalog payloads. Catalog and history tables use
composite media-type/ID keys because film and series numeric IDs can overlap.
Legacy film-only databases migrate automatically. Watched and hidden history is
independent of catalog publication and survives titles leaving and returning.

The frontend saves selections immediately and debounces number fields by 350 ms.
Preference writes are serialized; stale results and status responses do not
replace newer edits. Controls remain usable while saves complete.

## Code map

| Path | Responsibility |
| --- | --- |
| [`app.py`](../src/wanna_watch/app.py) | HTTP API, preferences, background refresh |
| [`tmdb.py`](../src/wanna_watch/tmdb.py) | Real provider discovery and title metadata |
| [`imdb.py`](../src/wanna_watch/imdb.py) | Official ratings download and ID matching |
| [`catalog.py`](../src/wanna_watch/catalog.py) | Collection, enrichment, publication |
| [`storage.py`](../src/wanna_watch/storage.py) | SQLite persistence, filtering, ranking |
| [`static/`](../src/wanna_watch/static/) | Responsive browser interface |
| [`verify.py`](../src/wanna_watch/verify.py) | Independent live source audit |

## Source limits

TMDB/JustWatch availability does not guarantee account entitlement, playback,
audio/subtitles, or access to every season of a series. Tags can be incomplete.
The watch-provider endpoint supplies a TMDB page, not direct playback links.

References: [TMDB movie discovery](https://developer.themoviedb.org/reference/discover-movie),
[TV discovery](https://developer.themoviedb.org/reference/discover-tv),
[watch providers](https://developer.themoviedb.org/reference/movie-watch-providers),
[official IMDb dataset](https://datasets.imdbws.com/title.ratings.tsv.gz).
