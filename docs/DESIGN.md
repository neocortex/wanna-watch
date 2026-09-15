---
name: Wanna Watch
description: Neon video store atmosphere for a real subscription catalog.
colors:
  bg: "#050d1d"
  panel: "#0a172b"
  line: "#2d4766"
  ink: "#f3f5ff"
  muted: "#b1c5e2"
  accent: "#4edcff"
  pink: "#ff67ce"
  sleeve: "#071324"
  field: "#0b192c"
  rating: "#ffe09b"
  primary-surface: "#170e2bc9"
  primary-hover: "#3b1641"
  primary-hover-ink: "#ffd8f4"
  chip-surface: "#0c1930d9"
  chip-ink: "#e3ecff"
typography:
  display:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "clamp(86px, 10.2vw, 160px)"
    fontWeight: 800
    lineHeight: 0.9
    letterSpacing: "-.025em"
  headline:
    fontFamily: "Barlow, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.25
  title:
    fontFamily: "Barlow, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Barlow, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Barlow, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  square: "0"
  rank: "2px"
  control: "3px"
  chip: "4px"
  sleeve: "5px"
spacing:
  tight: "6px"
  compact: "8px"
  control-gap: "9px"
  inset: "12px"
  section-gap: "18px"
  shelf-gap: "24px"
  deck-gap: "27px"
components:
  button-primary:
    backgroundColor: "{colors.primary-surface}"
    textColor: "{colors.pink}"
    rounded: "{rounded.control}"
    padding: "11px 18px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.primary-hover-ink}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 18px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    padding: "8px 0"
  field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  subscription-chip:
    backgroundColor: "{colors.chip-surface}"
    textColor: "{colors.chip-ink}"
    rounded: "{rounded.chip}"
    padding: "11px 15px"
  navigation:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    padding: "0 0 12px"
  poster-sleeve:
    backgroundColor: "{colors.sleeve}"
    rounded: "{rounded.sleeve}"
    padding: "12px"
---

# Design System: Wanna Watch

## Overview

**Creative North Star: "Neon video store"**

A cinematic night scene frames a practical personal catalog. Pink illuminated lettering and
cyan details recall a video-store frontage, while navy surfaces give real film artwork room
to carry the browsing experience. The user approved this world after comparing image concepts.

The interface pairs expressive italic display lettering with readable, compact controls.
Atmosphere belongs in the masthead and decorative storefront; catalog information remains live text.
This records the shipped implementation, with tokens extracted from
[style.css](../src/wanna_watch/static/style.css). The page composition and approved comp live in
[the surface brief](../.impeccable/surfaces/src-wanna-watch-static-index-html.md).

**Key Characteristics:**

- Illuminated pink display text and cyan interaction cues.
- Dark rectangular controls and closely framed poster sleeves.
- Real catalog imagery, restrained movement, and visible keyboard focus.

## Colors

The palette combines electric signage with blue-black architectural surfaces.

### Primary

The shared [SVG favicon](../src/wanna_watch/static/favicon.svg) reduces the angled wordmark to a bold
pink W with a cyan extrusion on night navy. It is served publicly so the sign-in page uses the same mark.

**Neon pink (`pink`)** carries the heading, brand, refresh button and selected navigation.

### Secondary

**Electric cyan (`accent`)** carries focus outlines, text actions, selection checks and the country indicator.

### Tertiary

**Warm rating gold (`rating`)** distinguishes genuine IMDb ratings from surrounding metadata.

### Neutral

**Night navy (`bg`)** is the canvas. **Panel navy (`panel`)** supports dialogs and missing posters.
**Sleeve navy (`sleeve`)** frames artwork; **field navy (`field`)** distinguishes editable values.
**Cool white (`ink`)**, **blue mist (`muted`)** and **slate line (`line`)** carry hierarchy and boundaries.
Translucent primary and chip surfaces keep the storefront visible without sacrificing label contrast.

**The Signage Rule.** Reserve luminous text shadows for the brand, display heading and selected tabs;
keep descriptions and filter labels readable without glow.

## Typography

Display lettering uses self-hosted **Barlow Condensed**, italic extra-bold, with sans-serif fallback.
Body, controls and titles use self-hosted **Barlow** in regular through bold weights.
Font declarations use `font-display: swap`; the display font is preloaded. Files and the OFL license
live in [static/fonts](../src/wanna_watch/static/fonts/).

The display token defines the desktop heading; its italic treatment, uppercase transformation, solid
split-tone highlight, pale rim and cyan/navy extrusion are component styling. On phones it uses
`clamp(72px, 18vw, 118px)`, line-height `.84`, and a `6ch` maximum width to create two lines. The
independently angled two-line wordmark uses a 65px display face, falling to 45px on phones. Card titles
use the title role, falling to 16px on phones. Filter labels and
metadata use the label role. Numeric ranks, rating values and counts use tabular numerals.
Synopses allow 70ch; catalog coverage allows 75ch.

## Layout

The centered shell is at most 1515px wide with 42px horizontal padding. The header is 104px high.
The masthead stacks the display title and compact refresh action so the storefront poster stays visible.
The desktop filter console places segmented media navigation beside four purpose-sized field columns and
an action column, with a vertical divider and expandable genres beneath.
Catalog shelves use four equal columns with 24px horizontal and 38px vertical gaps.
Cards align to the top and retain their natural metadata height.

At 1100px and below, shell padding becomes 28px, subscriptions wrap, fields use four equal columns,
and shelves use three columns. At 850px, media navigation sits above the filter controls. At 700px,
padding becomes 18px,
filters use two columns, poster shelves use two columns with 12px horizontal and 19px vertical gaps,
and card padding becomes 8px. At 360px, shell padding becomes 12px.
The provider picker is two columns on desktop and one on phones; its list scrolls within 38dvh.
The dialog is at most 570px wide, remains 12px from viewport edges, and is capped at 85dvh.

## Elevation & Depth

Depth comes from tonal navy gradients, thin internal dividers, neutral elevation and localized neon glow.
The subscription and filter console uses backdrop blur specifically to keep controls readable where the
decorative plate meets the catalog. The storefront is a
noninteractive background behind the shell, masked to fade at the bottom; it is not a catalog image.
The desktop plate occupies a 500px-high region with artwork sized to 500px high and shifted up 18px.
On phones it is 300px high, artwork is 320px high, shifted right by 32px and down by 20px, at `.62` opacity.

The heading combines a pale upper highlight, bright rim, stepped cyan/navy extrusion and diffuse pink light.
The wordmark gives each word its own angle and color-matched extrusion. Primary buttons retain a small
localized pink glow. Poster sleeves use neutral downward shadows, while the selected media segment uses an
inset line.
The undo toast uses `0 10px 35px #0009` to separate it from the scrollable catalog.
Exact motion and shadow values are also recorded in the [sidecar](../.impeccable/design.json).

## Shapes

Controls have small corners, chips are slightly rounder, and poster sleeves have the largest
repeated corner radius. Rank badges have tight corners; dialogs are square. Poster artwork stays
at a 2:3 ratio with clipped overflow. Avoid changing these practical rectangles into pill controls.
The display heading has a diagonal pink-to-cyan underline anchored at its right end below the punctuation,
with space for its lower left end above the refresh action.
The wordmark gives `wanna` and `watch` separate
angles and offsets, with three cyan speed lines completing the mark.
Icons are inline SVG with round joins and caps, normally 18px with a 1.7px stroke. Rating stars
are filled; decorative icons stay hidden from assistive technology while control labels remain text.

## Components

### Buttons

Primary actions have a pink outline, translucent surface and small glow. Secondary buttons have
a slate outline; hovering adds cyan borders and a darker fill. Text actions are cyan and underline
on hover. Buttons generally have a 44px minimum height; desktop refresh is 50px high and at least
238px wide, reducing to 44px high and 190px wide on phones. Disabled buttons use half opacity.
Keyboard focus has a 2px cyan outline offset by 4px.

### Chips

Subscription chips show actual selected services with SVG checks, a subtle vertical navy gradient, and muted
blue borders. They are 44px high on desktop and 38px on phones; they are informational, not action buttons.
The adjacent subscription editor remains a 44px-or-larger action with a dashed border.

### Cards / Containers

A tonal navy sleeve and inset blue line frame every real poster. A restrained diagonal reflection adds a
VHS-case glass cue without obscuring artwork. Missing artwork uses a textual placeholder,
never generated film art. Rank badges overlay the upper-left corner. Titles, year/runtime metadata,
language, genres, IMDb rating, providers, history actions and synopsis remain independent readable text.
A poster lifts by 5px on hover over 250ms only when the device supports hover and reduced motion is not
requested. The storefront develops over 800ms, the heading powers on over 750ms, and its underline traces
once over 680ms. The refresh icon turns only while a refresh is active. The entrance effects use
`cubic-bezier(.16,1,.3,1)`; control color changes take 150ms. Reduced motion shows the settled composition
and uses opacity for refresh progress.

### Inputs / Fields

Navy gradient fields have blue outlines, compact padding, visible labels and consistent 46px heights.
Released after is a native year select ranging from the previous calendar year to 1900, while preserving
an existing saved value outside that range. Phone numeric fields and selects use 16px text. Checkbox accents
are cyan. The services search
uses the darker canvas background. Errors use a plum panel with pale pink text and a visible border;
stale catalog notices use warm amber text. These states retain textual explanations.

### Navigation

Watch-state tabs use muted labels and transparent underline space; the active tab has pink text and
an underline. Film/series tabs use bordered rectangular controls with a translucent pink selected
surface. Both expose selection through `aria-pressed` and retain keyboard focus visibility.

### Storefront and assets

The generated [video-store.jpg](../src/wanna_watch/static/images/video-store.jpg) is decorative only. Its
lower-right marquee contains fictional, text-free poster art rather than a slogan. Its provenance is embedded
in the JPEG, with the original and edit prompts and build records in
[.impeccable/build](../.impeccable/build/). Real posters load from TMDB and link to IMDb;
service names and ratings come from the live catalog. The illustrated storefront is never evidence
of title availability. The approved image is a direction reference, not a pixel-exact rendering contract.

## Do's and Don'ts

### Do:

- **Do** preserve the neon video-store identity, real artwork and readable factual labels.
- **Do** keep rectangular control geometry, responsive poster columns and visible cyan focus.
- **Do** honor reduced motion and preserve artwork provenance and font licensing.

### Don't:

- **Don't** substitute generated posters, service names or scores for catalog data.
- **Don't** render functional text into imagery or remove accessible control names.
- **Don't** extend neon glow or movement to every label and card surface.
