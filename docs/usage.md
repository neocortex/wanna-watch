# Using Wanna Watch

Open **Subscriptions** beside **Refresh catalog** and choose the exact subscriptions you pay for, including ad-supported tiers or extra
channels where applicable, then select **Refresh catalog**. Browsing uses the
saved catalog while a refresh collects both films and series in the background.

Use the **Films** and **Series** tabs for separate ranked lists. Series use the
whole show's IMDb rating and premiere year; watched/hidden actions apply to the
whole show. Cards show season counts, and posters open IMDb.

## Filters

| Filter | Behavior |
| --- | --- |
| Services | Any checked saved subscription; All includes every subscription you pay for |
| Minimum IMDb votes | Inclusive minimum; initially 5,000 |
| Exclude genres | Hide titles matching any checked genre, including stand-up |
| Original language | English, German, French, Other, or Any |
| Released after | Year dropdown with an exclusive bound: 1990 includes 1991 onward |
| Maximum IMDb rating | Inclusive ceiling: 7.6 includes 7.6 and lower, still ranked descending |

English is the default language. Animation, Documentary, and Stand-up comedy are
excluded by default. **Reset filters** restores these defaults and clears the
year/rating limits, restores 5,000 minimum votes and all services, and keeps subscriptions and the selected list.

The sticky browsing bar keeps **Films**, **Series**, and **Filters** accessible while scrolling.
Filters opens one side panel on desktop and a bottom sheet on phones, including service selection.
Edit selections, then choose **Apply filters**. Cancel or Escape discards the draft and preserves your
scroll position. Applying updates the results without forcing a scroll. Incomplete or invalid ratings are not saved.
**Reset filters** is available only inside the panel and resets the draft; choose Apply filters to save it.

Service filtering does not change your paid subscriptions or refresh the catalog. An empty service
selection shows no results. Adding subscriptions in Subscriptions may require a refresh. Selecting Any year removes the year restriction. Maximum IMDb rating is a dropdown from
10.0 down to 6.0 in 0.1 steps, defaulting to 10.0 (no restriction).

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

## Subscription audio

With the optional Streaming Availability API key configured, English-original titles
may show **English may be unavailable** beside a provider. This means its reported
German subscription audio omits English. Check the service before playing; series
audio can differ by episode. Missing data produces no label, so an unlabeled provider
does not guarantee English audio. Netflix, Prime Video, and Disney+ base subscriptions
are supported; rental and channel audio are not applied to them.

## Appearance and accessibility

The interface uses an 80s neon video-store design, with a decorative storefront, fictional poster art,
layered navy control surfaces, and real TMDB movie posters. Filters and actions remain standard
keyboard-accessible controls. The subscription dialog supports Escape and returns focus to Subscriptions.
The storefront power-on, title illumination, refresh progress, and poster hover motion respect your device’s
reduced-motion preference. Fonts and decorative artwork are served locally; catalog data and poster sources
are unchanged.
