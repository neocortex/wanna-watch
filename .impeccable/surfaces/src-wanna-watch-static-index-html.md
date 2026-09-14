---
version: 1
slug: "src-wanna-watch-static-index-html"
primary_target: "src/wanna_watch/static/index.html"
related_targets: ["src/wanna_watch/static/style.css"]
---

# Catalog surface

Mode: Operate. Route: /. Preserve the real catalog, all filters and personal history.

## Direction contract

THESIS: A late-night video club whose illuminated sign leads directly into a useful catalog.
OWN-WORLD: Inky blue, warm white, electric cyan, hot pink, violet borders. Condensed italic
lettering contrasts with readable Barlow controls. Squared playback buttons and poster sleeves.
STORY: Select paid subscriptions, narrow films or series, browse IMDb-ranked posters, record history.
FIRST VIEWPORT: Slim brand masthead with “Less scrolling, more watching”; large single-line illuminated title
over the left two-thirds with a compact left-aligned refresh action; subscriptions above a layered horizontal
control console; watch-state navigation and real poster shelves visible
at desktop height. Mobile stacks the deck into two-column controls without truncating labels.
SIGNATURE: The storefront develops; the split-tone, extruded title powers on; its angled underline traces once
as a single
opening sequence; the refresh icon turns only during active work and poster sleeves lift on hover. Reduced
motion shows the settled design immediately and uses opacity for refresh progress.
FORM: Grounded candidates: rental membership card, VHS sleeve, neon video-club control deck (3),
cinema marquee, broadcast guide, record sleeve, arcade cabinet. Seed 9759ba9f.
Approved comp: .impeccable/mocks/neon-video-store.png. User selected neon on September 14, 2026.
The storefront on the right is a generated decorative plate with fictional text-free poster art in its
lower-right marquee. Real catalog posters and metadata replace
illustrative film details. Preserve useful factual copy and country indicator. Brand and heading are live text.
Approved-comp desktop target: brand at x 52/y 20; heading x 52/y 100; refresh y 263; subscriptions y 326;
filter deck y 400; catalog tabs y 510; four poster columns begin y 558.
Mobile retains the storefront behind the heading, wraps controls to two columns and shows two posters.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

IMPLEMENTED ADAPTATION: Shell max-width 1515px with 42px desktop gutters; a navy gradient filter console
uses purpose-sized fields and a native release-year dropdown; four, three, and two
poster columns at desktop, 1100px, and 700px respectively. Live subscriptions wrap and actual poster
art/metadata set catalog height. Comp comparison reported 59% difference; actual posters and five
subscriptions differ from the illustration. Font measurement could not isolate comp letters and the
automated build-phase gate has not passed. Final manual design review returned SHIP after SVG icon corrections;
do not claim pixel exactness or treat this record as an automated approval. Shipped tokens are in
docs/DESIGN.md and .impeccable/design.json.
