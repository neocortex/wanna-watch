# Using Wanna Watch

Choose the exact subscriptions you pay for, including ad-supported tiers or extra
channels where applicable, then select **Refresh catalog**. Browsing uses the
saved catalog while a refresh collects both films and series in the background.

Use the **Films** and **Series** tabs for separate ranked lists. Series use the
whole show's IMDb rating and premiere year; watched/hidden actions apply to the
whole show. Cards show season counts, and posters open IMDb.

## Filters

| Filter | Behavior |
| --- | --- |
| Minimum IMDb votes | Inclusive minimum; initially 5,000 |
| Exclude genres | Hide titles matching any checked genre, including stand-up |
| Original language | English, German, French, Other, or Any |
| Released after | Exclusive year bound: 1990 includes 1991 onward |
| Maximum IMDb rating | Inclusive ceiling: 7.6 includes 7.6 and lower, still ranked descending |

English is the default language. Animation, Documentary, and Stand-up comedy are
excluded by default. **Reset filters** restores these defaults and clears the
year/rating limits, keeping subscriptions, the selected list, and minimum votes.

Selections update immediately. Year and rating fields update after a 350 ms typing
pause; incomplete or invalid numbers are not saved. A blank number field removes
that restriction. The rating ceiling accepts 1.0–10.0 in 0.1 steps.

Other languages means known languages outside English, German, and French.
Missing language only matches Any; missing years are omitted when a year limit is
active. Language is the title's original language, not available dubbing.

## Personal history

**Watched**, **Hide**, **Restore**, and **Undo** persist on the server. History stays
saved even if a title leaves a subscription and later returns. Films and series
with the same numeric TMDB ID keep separate histories.

## Phone access

Start the server with:

```bash
uv run wanna-watch --host 0.0.0.0
```

Open `http://YOUR_MAC_LAN_IP:8000` in Safari on the same Wi-Fi network. Optionally
use Share → Add to Home Screen. The Mac must remain awake with the server running.
This is a local web app, not an offline PWA or a hosted service.

## Data and backups

`data/wanna-watch.sqlite3` contains the catalog, preferences, and history.
`data/title.ratings.tsv.gz` and `data/ratings-source.json` cache IMDb ratings.
Set `WANNA_WATCH_DATA_DIR` in the shell environment to use another directory.

Stop the server before copying the data directory for a backup. Do not delete the
SQLite database when clearing generated test output. After upgrading an older
catalog, refresh it to populate newly supported metadata and series.
