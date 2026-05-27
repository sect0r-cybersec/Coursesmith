---
name: coursesmith-cert
description: Generates a personalised PNG certificate of completion for a finished Coursesmith study guide. Reads manifest.json, refuses if any chapter is still pending, prompts the user for the recipient name and (optionally) the light/dark variant, auto-derives a neon accent colour from the book's cover, extracts the author from PDF metadata or the title page, renders a bundled HTML template through headless Chromium, writes certificate.png into the study-guide folder, and re-renders the roadmap to link it. Use when the user says "generate my certificate", "I'm done with this book", "make me the cert", or "regenerate my cert with a different name/theme". Not for use mid-course - direct them to coursesmith-generate for pending chapter work.
---

# Coursesmith - Cert

Produces a PNG certificate of completion for a study-guide folder where every chapter is `status: "ready"`. Standalone skill - user invokes it manually after finishing the book.

## Preconditions

Before doing anything else, locate `manifest.json` in the folder the user named (or referenced). If no manifest exists, stop and tell the user:

> No study guide folder found here. Either point me at the folder, or run `coursesmith-init` first if you haven't scaffolded one.

Then read the manifest and check every chapter has `status: "ready"`. If any are still `pending`, refuse and list them:

> Some chapters are still pending: {N}, {M}, {O}. Finish them with `coursesmith-generate` first, then come back for the cert.

Do not generate a partial-completion certificate.

## What the user is asked

Two questions, in order. Skip either if the user has already answered it in their initial prompt.

1. **Name on the certificate.** Single text field. Free-form. The user controls capitalisation - do not auto-format.
2. **Theme: light or dark? (default: dark)**. Two-option pick with dark as the default. The user can also say "use the light one" or "dark, obviously" in their initial prompt and skip the question.

If the user has explicitly said "regenerate" or "redo my cert", read the existing `manifest.certificate.name` and `manifest.certificate.theme` as defaults and only ask if they want to override.

## Generating the cert

Run the bundled script:

```bash
python {coursesmith-cert-skill-dir}/scripts/render_certificate.py \
  --manifest {output_dir}/manifest.json \
  --name "{user-supplied name}" \
  --theme {dark|light}
```

Optional flags the user might ask for:
- `--accent "#ff4136"` - override the cover-derived accent with an explicit hex
- `--date "26 May 2026"` - override the completion date (defaults to today, British format)

The script auto-installs `playwright` / `Pillow` / `pypdf` if missing, extracts the cover (pdfimages → pdftoppm fallback), derives a neon accent in OKLCH, scrapes the author from PDF metadata or the title page, generates a deterministic cert ID (`CSM-{sha256(slug|date)[:4]}-{year}`), substitutes tokens into `templates/certificate.html`, renders via Playwright Chromium at 1200x800, writes `certificate.png`, and updates the manifest + roadmap. Implementation details live in `scripts/render_certificate.py` and `references/neonification-rules.md`.

Tell the user where the file landed:

> Certificate written to `{output_dir}/certificate.png`. The roadmap now links to it from the top of `index.html`. Cert ID: `CSM-XXXX-YYYY`.

## Refine mode

The user wants to regenerate with a tweak.

| User asks for | What to do |
|---|---|
| "regenerate with name X" | Re-run with `--name X`. Cert ID stays the same (it's date-derived, not name-derived). |
| "make it light" / "make it dark" | Re-run with `--theme light` / `--theme dark`. |
| "use #ff4136 instead" | Re-run with `--accent "#ff4136"`. Manifest records `accent_source: "override"`. |
| "use a different date" | Re-run with `--date "..."`. Cert ID changes (date-derived). |

After regenerating, the script updates `manifest.json` automatically. Do not re-render the roadmap manually - the script handles it.

## What this skill never does

- Generate certificates for unfinished study guides.
- Modify the certificate template programmatically. The user edits `templates/certificate.html` directly if they want design changes; the skill only does string substitution.
- Touch chapter content, Anki decks, lab files, or anything else inside `{output_dir}/chapters/`.
- Generate certificates without a recipient name. If the user hasn't given one, ask before running the script.

## Bundled files

| File | Purpose |
|---|---|
| `templates/certificate.html` | Self-contained HTML template, both dark and light palettes via `[data-theme="..."]` |
| `scripts/render_certificate.py` | Entry script: orchestrates extraction, substitution, screenshot, manifest update, roadmap re-render |
| `scripts/extract_accent.py` | Cover image to neon hex (and light variant); no external dependencies beyond Pillow |
| `scripts/extract_author.py` | PDF metadata to title-page text scrape, with a blacklist |
| `references/neonification-rules.md` | OKLCH lightness + chroma thresholds, documented |

## Running outside Claude Code

Assumes persistent filesystem; for ephemeral environments use the zip-handover fallback in `coursesmith-init/references/non-claude-code-fallback.md`.

## When things go wrong

- **Playwright Chromium install fails** (offline or proxy): the script falls back to telling the user "Chromium needs to be installed once - run `python -m playwright install chromium` and re-invoke." Do not try to work around this; the cert needs a real browser to render the glass and gradients correctly.
- **Cover extraction produces a bad colour** (e.g. a near-black hue from a dark cover): the user can re-run with an explicit `--accent` to override. The skill mentions this on first run if the manifest records `accent_source: "default"` and the cover extraction returned nothing.
- **Title-page scrape returns a clearly wrong author** (rare but possible): the user re-runs with a manual edit. Future improvement: a `--author` flag to override directly, currently out of scope.
- **Manifest is missing `source_pdf`** (manual hand-editing gone wrong): refuse and tell the user the manifest needs the original `source_pdf` path to extract the cover. They can re-run `coursesmith-init` against the original PDF to rebuild the manifest, or edit it manually.

## Output checklist

Before declaring the cert done, verify:

- [ ] `certificate.png` exists in `{output_dir}/`
- [ ] `manifest.json` has a `certificate` block with `name`, `id`, `accent`, `accent_source`, `theme`, `author_used`, `path`, `generated_at`
- [ ] `manifest.last_modified` was bumped
- [ ] `index.html` (roadmap) has the certificate card pinned at the top, linking to `certificate.png`
- [ ] The user knows the cert ID and the file path
