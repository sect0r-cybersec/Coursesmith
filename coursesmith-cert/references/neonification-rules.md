# Neonification rules

Reference for the OKLCH thresholds in `extract_accent.py`. Documenting these
so future tweaks don't have to be re-derived from scratch.

## The premise

A cover-derived colour rarely makes a good accent on its own.

- Photographic covers are dark or muddy.
- Title-bar colours (the "hero" colour we want) often have low chroma.
- The same colour reads very differently on dark vs light backgrounds.

We don't reproduce the cover's exact swatch. We extract just the **hue** and
synthesise the lightness and chroma ourselves. The cert always feels
electric; the cover decides the *colour* of the electricity.

## Why OKLCH, not HSL

HSL lightness is perceptually wrong. `hsl(60, 100%, 50%)` (yellow) appears
far brighter than `hsl(240, 100%, 50%)` (blue) despite identical L. If we
neonified in HSL with a fixed lightness, red certs would glow and blue
certs would look dull.

OKLCH is perceptually uniform: a fixed `L` produces consistent perceived
brightness across hues. This is exactly what we want.

## Thresholds in use

| Parameter | Value | Why |
|---|---|---|
| `SATURATION_FLOOR` | 0.25 | Reject near-greys; a cover with a desaturated grey-blue title bar should fall back to default rather than produce a muddy cert |
| `VALUE_FLOOR` | 0.15 | Reject near-blacks; otherwise a black-cover book gets a dim near-black accent |
| `VALUE_CEIL` | 0.90 | Reject near-whites; otherwise a white-cover book gets a near-white accent |
| `TOP_BAND_FRACTION` | 0.25 | Sample only the top 25% on the first pass; tech-book covers usually put the hero colour in the title-bar zone |
| `QUANTIZE_COLOURS` | 16 | Cluster the cover into 16 representative colours; finer doesn't help, coarser misses accent colours |
| `L_DARK` | 0.72 | OKLCH lightness for the dark-cert variant; produces a "neon emitting light" feel on a dark surface |
| `L_LIGHT` | 0.45 | OKLCH lightness for the light-cert variant; readable on a light surface (WCAG-AA against #f6f7fb for most hues) |
| `C_TARGET` | 0.20 | OKLCH chroma; pushes the colour to "maximum purity" without clipping the sRGB gamut for most hues |
| `C_RETRY` | 0.18 | Fallback chroma when the first attempt clips substantially (e.g. extreme blues at high L) |

## Alpha levels for dim and glow

| Variant | dim alpha | glow alpha |
|---|---|---|
| Dark | 0.15 | 0.40 |
| Light | 0.12 | 0.25 |

Light alphas are lower because the surface is already light - the same alpha
that tints a dark background subtly would wash out a light background.

## When to revisit

- If a particular book produces a bad accent, prefer adding the user's
  `--accent` override to the SKILL.md docs rather than tweaking thresholds.
- If users systematically complain about dim-mode contrast in certain hues
  (likely blues and purples on dark), `L_DARK` can drop to 0.68 to reduce
  perceived washout.
- If users systematically complain about light-mode contrast on yellows,
  `L_LIGHT` can drop to 0.42.

## Default fallback

When extraction yields no vivid cluster, the palette falls back to
Coursesmith neon green:

- Dark hex: `#7cf07c`
- Default hue (OKLCH): `145.0`

The light variant is neonified from that same hue at `L_LIGHT`, giving
roughly `#15803d` (the same target the course's light-mode CSS uses for
its accent).
