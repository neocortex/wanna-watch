# Wanna Watch

Find unseen films and series included in your German subscriptions, ordered by **IMDb**
rating. A personal web app that works in desktop and phone browsers.

The neon video-store interface uses locally hosted fonts and decorative artwork,
with keyboard-accessible controls and support for reduced motion.

The app uses real TMDB/JustWatch availability and IMDb's official ratings
dataset. It starts empty; no demonstration titles or invented availability are
loaded. See the [documentation](#documentation) for usage and development details.

## Run locally

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

Obtain a **TMDB API Read Access Token** from
[your TMDB API settings](https://www.themoviedb.org/settings/api), then put it in
`.env`:

```dotenv
TMDB_READ_TOKEN=your_read_access_token
```

Use the read access token, not the shorter API key. The token stays on the server;
the browser never receives it. `.env`, downloads, and personal history are ignored
by Git. A changed token is picked up without a server restart.

```bash
uv run wanna-watch
```

Open **http://127.0.0.1:8000**, choose your actual subscriptions, and select
**Refresh catalog**. Choose exact plans, including ad-supported tiers or extra
channels where applicable. Only subscription (`flatrate`) offers are included;
rental and purchase offers are excluded. A full refresh checks every discovered
film and series before publication and can take tens of minutes. Browsing uses the saved catalog and does not wait for API calls.
Later full refreshes perform the same checks in the background while the saved
catalog remains available.

To open it on your iPhone on the same trusted Wi-Fi network:

```bash
uv run wanna-watch --host 0.0.0.0
```

Visit `http://YOUR_MAC_LAN_IP:8000` in Safari. You can add that page to your Home
Screen from Safari's Share menu. Your Mac and the server must stay running.
This is a single-user LAN app with no authentication; do not expose its port to
the public internet. Native iOS packaging and cloud hosting are not implemented.

## Documentation

- [Usage and filters](docs/usage.md)
- [Architecture and data sources](docs/architecture.md)
- [Testing and live verification](docs/testing.md)
- [Changelog](docs/CHANGELOG.md)

## Development checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run playwright install chromium
uv run pytest
```

See the [testing guide](docs/testing.md) for live-data prerequisites and audit commands.
Keep `.env` and `data/` private; both are ignored by Git. Commit `uv.lock` and
`.env.example` so the environment and setup remain reproducible.

## Attribution

Availability data is supplied by **JustWatch** through **TMDB**. This product uses
the TMDB API but is not endorsed or certified by TMDB. Ratings and vote counts are
from IMDb's official dataset. Review source terms before distribution or commercial
use: [TMDB FAQ](https://developer.themoviedb.org/docs/faq),
[JustWatch attribution](https://developer.themoviedb.org/reference/movie-watch-providers),
and [IMDb data usage](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX).
