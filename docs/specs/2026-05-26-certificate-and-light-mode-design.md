# Certificate skill + course light mode — design

**Date:** 2026-05-26
**Author:** Coursesmith maintainer (with Claude brainstorming)
**Status:** Locked, ready for implementation

## Understanding summary

Two changes to the Coursesmith skill set:

1. **A new standalone skill, `coursesmith-certificate`**, that produces a personalised PNG certificate of completion for a finished study guide. Reads the existing `manifest.json`, refuses if any chapter is not `status: "ready"`, prompts the user for a recipient name, derives a neon accent colour from the book cover, extracts the author from PDF metadata or the title page, renders a bundled HTML template through headless Chromium (Playwright), drops `certificate.png` into the study-guide folder, and re-renders the roadmap to link it.
2. **Light mode for the course pages**, defaulting to OS preference with a manual toggle persisted in `localStorage`. Touches `coursesmith-init` (styles, roadmap header, sidebar/script) and `coursesmith-generate` (chapter topbar). The certificate stays dark-only because it's a rendered artefact, not a live page.

### Why
Closes the loop on the Coursesmith workflow (init scaffolds, generate fills, certificate marks "done"); gives users a tangible artefact for self-directed study. Light mode reduces eye strain for users not on dark-mode displays.

### Who it is for
Single user (the author), studying technical non-fiction books over multiple sessions on local disk. No multi-tenancy, no auth, no network beyond Google Fonts CDN.

## Assumptions

- **Performance** is non-critical. Cert generation is ~3–6s including Chromium cold start. Light-mode toggle is instant.
- **Privacy:** all artefacts are local. The recipient's name is written to a local PNG. Google Fonts CDN is hit for JetBrains Mono unless fonts are inlined as base64 later.
- **Reliability:** the cert script auto-installs `playwright`, `Pillow`, `pypdf` on first run and triggers `playwright install chromium` if needed, mirroring `generate_anki.py`'s pattern.
- **Idempotence:** re-running the cert overwrites `certificate.png` and updates the manifest. Cert ID is deterministic from `book_slug + completion_date`, so the same person re-running gets the same ID; different name on the same day = same ID.
- **Date format:** British, `"26 May 2026"`. Override via `--date` flag.
- **Long-name handling:** the recipient name field uses a clamp so names that exceed ~24 chars at 68px shrink rather than overflow the plaque.
- **Backward compatibility:** existing study guides keep working in dark mode. The light-mode toggle picks up on the next `coursesmith-generate` run that re-renders the roadmap/chapter pages.
- **No multi-tenancy or auth.** Single user.

## Decision log

| Decision | Chosen | Alternatives considered | Why |
|---|---|---|---|
| Skill location | New `coursesmith-certificate` skill | Inside init (placeholder + fill); inside generate (auto on last chapter); inside generate (opt-in) | User needs to pass a name; cleaner to isolate; iterates independently |
| Render method | HTML/CSS + Playwright Chromium screenshot | wkhtmltoimage; Pillow compositing; SVG + cairosvg | Pixel-perfect, iterate-in-browser, matches existing HTML-first stack |
| Handoff | Generate prints a hint; user invokes certificate manually | Auto-invoke after last chapter; cert skill auto-detects on any run | Zero coupling; minimal edit to generate; user stays in control |
| Content | Name + book title + author + completion date + cert ID | + chapter/subsection/card counts; + signature line | Smallest viable cert; no init schema changes |
| Output location | `{output_dir}/certificate.png` + roadmap card | PNG only, no roadmap edit; PNG + HTML viewer; PNG + PDF | Discoverable without extra files |
| Placeholders | `{{NAME}}`, `{{BOOK_TITLE}}`, `{{BOOK_AUTHOR}}`, `{{COMPLETION_DATE}}`, `{{ACCENT_COLOR}}`, `{{ACCENT_DIM}}`, `{{ACCENT_GLOW}}`, `{{CERT_ID}}` | Smaller set; richer set with counts | Matches content decision |
| Accent source | Cover-derived, neonified, fall back to default green | Static default; ask at cert time; store in manifest at init | Per-book identity without per-book input; deterministic |
| Neonification rule | OKLCH lightness ≥ 0.65–0.70, max chroma; dim/glow at 0.15α / 0.40α | Use raw cover colour | Cover colours are often muted/dark; neon zone is a perceptual treatment |
| Cover extraction | `pdfimages` first, `pdftoppm` fallback | Either alone | Best-of-both for speed and reliability |
| Cluster filtering | Saturation > 0.25, luminance 0.15–0.90; two-pass (top 25% banner first, then full cover) | Most-common-colour-period; single-pass | Captures hero colours in title-bar zones; skips muddy fallbacks |
| Colour-space choice | OKLCH for neonification | HSL | Perceptually uniform — fixed L produces consistent brightness across hues |
| Author source | PDF metadata → title-page scrape → omit, with `"by "` prefix | Title-page only; ask at init; ask at cert time | Most automatic; degrades gracefully |
| Metadata blacklist | Adobe/InDesign/Quark/LaTeX/MS Word/Microsoft/unknown/admin/user/untitled; emails; > 80 chars | Trust metadata as-is | False positives worse than omission |
| Empty author handling | Strip the whole div, not just blank it | Leave empty div | Keeps spacing tight |
| Footer right slot | Auto-generated Cert ID `CSM-XXXX-YYYY` | Leave empty; "Issued by Coursesmith"; user-supplied note | Adds verifiability feel without extra prompts |
| Cert ID basis | `sha256("{book_slug}\|{completion_date}")[:4]` | Include name; full random; include accent | Deterministic per cert instance; same person re-running gets same ID |
| Canvas | 1200×800 (matches the locked template) | 2480×1754 (A4 @ 2x) | Lighter file, sharp enough for screen |
| Skill file shape | One entry + two helper scripts + one template + one reference | Single fat script; package with `__init__.py` | Matches existing skills; each helper has a clean single responsibility |
| Dependencies | Playwright, Pillow, pypdf, auto-installed on first run | Bundle colorthief; bundle a colour-conversion lib | Quantise + inline OKLCH conversion, no extra dep |
| Light-mode toggle mechanism | Manual button, defaults to OS preference, localStorage override | Static dark; OS-only no button; three-state Auto/Dark/Light | Modern behaviour; respects user OS; one extra click to pin |
| Toggle placement | Topbar on chapter pages + roadmap header | Sidebar; floating; roadmap-only | Visible everywhere without crowding sidebar |
| Palette strategy | Inverted with toned-down accent (#7cf07c → #15803d) | Keep neon accent; sepia/warm; pure b/w high contrast | Faithful identity translation; WCAG-AA on white; minimal scope |
| Certificate behaviour under light mode | Stays dark-only | Mirror user preference | Cert is a rendered artefact; consistent regardless of viewer |
| Anti-flash strategy | Inline `<head>` script sets `data-theme` before paint | Accept the flash; CSS-only | Single-line solution; standard pattern |
| Roadmap card markup ownership | Shared snippet in `coursesmith-init/templates/roadmap-certificate-card.html`, read by both renderers | Duplicate inline in each skill | Single source of truth for the card markup |

## Final design

### A. New skill: `coursesmith-certificate`

**File layout:**
```
coursesmith-certificate/
├── SKILL.md
├── scripts/
│   ├── render_certificate.py   # entry
│   ├── extract_accent.py       # cover → neon hex (no extra deps)
│   └── extract_author.py       # metadata → title-page → omit
├── templates/
│   └── certificate.html        # the locked template + {{CERT_ID}} slot
└── references/
    └── neonification-rules.md  # OKLCH thresholds documented
```

**`SKILL.md` description (front matter):**

> Generates a personalised PNG certificate of completion for a finished Coursesmith study guide. Reads `manifest.json`, refuses if any chapter is still `pending`. Prompts the user for the recipient name, auto-derives a neon accent colour from the book's cover, extracts the author from PDF metadata or the title page, renders a bundled HTML template through headless Chromium, writes `certificate.png` into the study-guide folder, and re-renders the roadmap to link it. Use when the user says "generate my certificate", "I'm done with this book", or "make me the cert". Not for use mid-course — direct them to `coursesmith-generate` for pending chapter work.

**`render_certificate.py` flow:**

1. Auto-install `playwright`, `Pillow`, `pypdf`; run `playwright install chromium` if needed.
2. Load `manifest.json`. Refuse if any chapter is not `status: "ready"`; list the pending ones.
3. Resolve accent: `--accent` override, else `extract_accent.extract_from_pdf(source_pdf)`, else default green.
4. Resolve author: `extract_author.extract_from_pdf(source_pdf)` returns a string or `None`.
5. Generate cert ID: `f"CSM-{sha256(f'{book_slug}|{date_iso}').hexdigest()[:4].upper()}-{date_iso[:4]}"`.
6. Substitute tokens in `templates/certificate.html`. If author is `None`, regex-strip the `<div class="book-author">...</div>` element.
7. Launch Playwright at viewport 1200×800, load the file URL, wait for fonts, screenshot to `{output_dir}/certificate.png`.
8. Add `certificate` block to manifest (see schema below); bump `last_modified`.
9. Re-render `{output_dir}/index.html` using the shared roadmap-card snippet.
10. Print absolute path to the PNG. Exit 0.

**Invocation:**
```bash
python {certificate-skill-dir}/scripts/render_certificate.py \
  --manifest {output_dir}/manifest.json \
  --name "Jane Doe" \
  [--accent "#ff4136"] \
  [--date "26 May 2026"]
```

**`extract_accent.py` algorithm:**
1. Cover via `pdfimages -f 1 -l 1 -png`, fall back to `pdftoppm -f 1 -l 1 -png -r 100`.
2. Two-pass: top 25% banner zone first, then full cover.
3. Resize to 200px wide, quantize to 16 colours, walk palette + histogram.
4. Keep entries with HSV saturation > 0.25 and 0.15 < value < 0.90; first kept entry is the winner.
5. RGB → OKLCH (inline conversion). Take hue only.
6. Neonify: `L = 0.72`, `C = 0.20`, hue preserved. Convert back to sRGB hex. If channels clip substantially, retry once at `C = 0.18`.
7. Compose `(hex, rgba_at_0.15, rgba_at_0.40)`.
8. Fallback: `("#7cf07c", "rgba(124,240,124,0.15)", "rgba(124,240,124,0.40)")`.

**`extract_author.py` algorithm:**
1. `pypdf` metadata: `/Author`, reject if empty/blacklisted/contains `@`/> 80 chars. Try `/Publisher` next.
2. If none: `pdftotext -f 1 -l 3 -layout`, look for `by X` lines, then title/author line pairs, then known publisher imprints.
3. Sanitise (strip "by ", collapse whitespace, title-case if all caps, cap at 60 chars).
4. Return `None` if nothing trustworthy found.

### B. Manifest schema addition

```json
{
  "certificate": {
    "name": "Jane Doe",
    "id": "CSM-A7F2-2026",
    "accent": "#f5c842",
    "accent_source": "cover",
    "author_used": "Mitchell Ashley",
    "path": "certificate.png",
    "generated_at": "2026-05-26T14:32:00Z"
  }
}
```

`accent_source` is one of `"cover"`, `"override"`, `"default"`. `author_used` is the printed string or `null`. `path` is relative to the study-guide folder. Presence of `manifest.certificate` is the signal to inject the Certificate card on the roadmap.

### C. Edits to `coursesmith-generate`

1. **Hint after the final chapter:** in step 13 of the per-chapter flow, when no chapters remain `pending` after this one:
   > Chapter {N} is done — that's the last one. Every chapter is now ready. Run `coursesmith-certificate` whenever you want your certificate of completion.

   Same hint fires at the end of loop mode.

2. **Topbar toggle button:** `templates/chapter.html` topbar gets `<button class="theme-toggle" aria-label="..."></button>` as a sibling to the breadcrumb.

3. **Roadmap re-render:** read the shared snippet `coursesmith-init/templates/roadmap-certificate-card.html` and inject when `manifest.certificate` is present.

### D. Roadmap card markup

`coursesmith-init/templates/roadmap-certificate-card.html`:
```html
<div class="roadmap-node certificate-node">
  <a class="roadmap-card certificate-card ready" href="certificate.png" target="_blank">
    <div class="chapter-num">CERTIFICATE</div>
    <div class="chapter-title">{{name}} · {{book_title}}</div>
    <div class="chapter-meta">
      <span class="status-badge ready">
        <span class="status-icon complete">✓</span> Completed
      </span>
      <span>{{id}}</span>
      <span>Issued {{date_human}}</span>
    </div>
  </a>
</div>
```

CSS addition in `styles.css`:
```css
.certificate-card { border-color: var(--accent-glow); margin-bottom: 1.5rem; }
.certificate-node:not(:last-child)::after,
.certificate-node:not(:last-child)::before { display: none; }
```

### E. Light-mode plan (course pages only)

**Files touched:**
- `coursesmith-init/templates/styles.css`
- `coursesmith-init/templates/script.js`
- `coursesmith-init/templates/roadmap.html`
- `coursesmith-generate/templates/chapter.html`

**Anti-flash inline `<head>` script** (added to `roadmap.html` and `chapter.html`):
```html
<script>
  (function () {
    var saved = localStorage.getItem('coursesmith-theme');
    if (saved === 'light' || saved === 'dark') {
      document.documentElement.setAttribute('data-theme', saved);
    }
  })();
</script>
```

**Palette tokens (light):**

| Token | Dark | Light |
|---|---|---|
| `--bg-base` | `#0a0e1a` | `#f6f7fb` |
| `--bg-deep` | `#06080f` | `#e8ecf3` |
| `--bg-glass` | `rgba(20,26,42,0.55)` | `rgba(255,255,255,0.65)` |
| `--bg-glass-hover` | `rgba(28,36,56,0.7)` | `rgba(255,255,255,0.85)` |
| `--bg-elevated` | `rgba(30,40,60,0.4)` | `rgba(232,236,243,0.6)` |
| `--border-subtle` | `rgba(255,255,255,0.06)` | `rgba(10,14,26,0.06)` |
| `--border-default` | `rgba(255,255,255,0.12)` | `rgba(10,14,26,0.12)` |
| `--border-strong` | `rgba(255,255,255,0.22)` | `rgba(10,14,26,0.22)` |
| `--text-primary` | `#f5f7fb` | `#0a0e1a` |
| `--text-secondary` | `#b8c2d6` | `#3a4459` |
| `--text-muted` | `#7682a0` | `#6b7591` |
| `--text-code` | `#d4dcf0` | `#1e293b` |
| `--accent` | `#7cf07c` | `#15803d` |
| `--accent-dim` | `rgba(124,240,124,0.15)` | `rgba(21,128,61,0.12)` |
| `--accent-glow` | `rgba(124,240,124,0.35)` | `rgba(21,128,61,0.25)` |

**Atmospheric layers in light mode:** body radial-gradient blooms drop to 0.04–0.06 alpha; glass surfaces add a soft drop shadow (`0 1px 3px rgba(10,14,26,0.05), 0 4px 12px rgba(10,14,26,0.06)`); accent-glow ring on "ready" cards becomes much subtler.

**Code blocks in light mode:** `pre` background switches to `#f1f5f9`; Prism token overrides for comment/keyword/string/number/function/operator (see Section 7 of the brainstorm).

**Quiz / status in light mode:** `status-progress` shifts to `#b45309`, `status-error` to `#b91c1c`; selected/correct/incorrect option backgrounds adjust to keep 3:1 contrast.

**CSS structure:**
```css
:root { /* dark tokens (existing) */ }
@media (prefers-color-scheme: light) { :root { /* light tokens */ } }
:root[data-theme="light"] { /* light tokens, repeated */ }
:root[data-theme="dark"]  { /* dark tokens, repeated */ }
/* Component tweaks scoped to [data-theme="light"] and @media light */
```

**`script.js` addition (~25 lines):** reads `coursesmith-theme` from localStorage, falls back to `prefers-color-scheme`, sets `data-theme`, swaps sun/moon icon on `.theme-toggle` buttons, updates ARIA labels. Click handler flips and persists.

**Markup insertion points:** top-right of `.roadmap-header`; top-right of `.topbar` on chapter pages.

## Risks acknowledged

- **Cover extraction may produce odd hues** for covers with no clear hero colour (mostly black, photographic). Mitigation: fallback to default green; the user can pass `--accent` to override.
- **PDF author metadata is unreliable.** Mitigated by blacklist + scrape fallback + graceful omission.
- **Google Fonts CDN dependency** on the cert template. Acceptable for now; flagged as a future improvement (inline as base64).
- **Light-mode Prism token colours are hand-picked** — may not match every code language perfectly. Iterate based on what looks off.
- **Long recipient names** are handled by CSS clamp; very long names (50+ chars) may still look cramped.

## Exit criteria met

- [x] Understanding Lock confirmed
- [x] One design approach explicitly accepted (single approach, no rejected alternatives in flight)
- [x] Major assumptions documented
- [x] Key risks acknowledged
- [x] Decision Log complete

Ready for implementation.

---

## Amendments (2026-05-26, post-lock)

Two changes requested at implementation handoff:

### 1. Skill rename

`coursesmith-certificate` → `coursesmith-cert` everywhere.

Touches:
- New skill directory: `coursesmith-cert/` (not `coursesmith-certificate/`)
- The hint added to `coursesmith-generate` step 13 names `coursesmith-cert`
- `SKILL.md` description and references use `coursesmith-cert`
- Shared snippet remains at `coursesmith-init/templates/roadmap-certificate-card.html` (filename unchanged — refers to the card, not the skill)

### 2. Light/dark certificate variant

The skill now asks the user at invocation time: "Light or dark certificate? (default: dark)". Default is dark; light is opt-in per cert.

**Touches:**

- **`render_certificate.py`** gains a `--theme dark|light` flag, defaulting to `dark`. Skill prompts the user and passes the chosen value.
- **`certificate.html` template** gains `[data-theme="light"]` CSS overrides for its `:root` palette, mirroring the course CSS pattern. Renderer sets `<html data-theme="...">` before screenshot.
- **`extract_accent.py`** returns a richer tuple: `(dark_hex, dark_dim, dark_glow, light_hex, light_dim, light_glow)`. The light variant is the same hue at OKLCH `L=0.45` (vs `L=0.72` for dark), chroma maxed for that lightness. Dim alpha 0.12, glow alpha 0.25 (vs 0.15/0.40 on dark).
- **Manifest schema** gains `theme: "dark" | "light"` inside the `certificate` block.
- **Roadmap card** unchanged — still links to `certificate.png` regardless of theme.

**Template palette tokens (light cert):**

| Token | Dark cert (existing) | Light cert (new) |
|---|---|---|
| `--bg` | `#0a0e1a` | `#f6f7fb` |
| `--bg-deep` | `#06080f` | `#e8ecf3` |
| `--glass` | `rgba(20,26,42,0.60)` | `rgba(255,255,255,0.70)` |
| `--border-subtle` | `rgba(255,255,255,0.06)` | `rgba(10,14,26,0.06)` |
| `--border-default` | `rgba(255,255,255,0.12)` | `rgba(10,14,26,0.12)` |
| `--border-strong` | `rgba(255,255,255,0.22)` | `rgba(10,14,26,0.22)` |
| `--text-primary` | `#f5f7fb` | `#0a0e1a` |
| `--text-secondary` | `#b8c2d6` | `#3a4459` |
| `--text-muted` | `#7682a0` | `#6b7591` |
| `--accent` | cover-derived neon @ L=0.72 | same hue @ L=0.45 |
| `--accent-dim` | rgba(...) @ 0.15α | rgba(...) @ 0.12α |
| `--accent-glow` | rgba(...) @ 0.40α | rgba(...) @ 0.25α |

The light cert's plaque gets a subtle drop shadow added under `[data-theme="light"]` to compensate for the loss of contrast against the (now-light) bg. The decorative SVG line opacities are unchanged — they're already low enough to read on light.

### Decision log additions

| Decision | Chosen | Alternatives | Why |
|---|---|---|---|
| Cert theme selection | Ask at invocation, default dark, `--theme` flag | Always dark; always match course light/dark; per-book in manifest | User control without burying the option; preserves backward-compat default |
| Light cert accent | Same cover-derived hue, lower OKLCH lightness (L=0.45) | Static dark green (#15803d); same neon hex unadjusted | Preserves per-book identity in the light variant; readable on white |
| Theme persistence in cert | Stored in manifest, re-runs re-use unless overridden | Always ask, never store | One-cert-per-book usually; storing avoids re-prompting on regeneration |

