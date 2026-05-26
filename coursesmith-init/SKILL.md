---
name: coursesmith-init
description: One-time setup for a Coursesmith study guide. Reads a non-fiction book PDF off disk, extracts the table of contents, derives chapter page ranges, scaffolds a TryHackMe/HTB-Academy-style HTML course folder (manifest.json, roadmap index.html, styles, placeholder pages for every chapter), then hands off to coursesmith-generate for chapter 1. Use ONLY for the first run on a new book ("turn this book into a study guide", "start a course from this PDF", "make me a TryHackMe-style course from this book"). For every subsequent run (next chapter, refine, whole-book loop) use coursesmith-generate instead.
---

# Coursesmith - Init

Sets up the on-disk scaffold for an interactive course built from a non-fiction book, then hands off to `coursesmith-generate` to produce chapter 1.

This is **one-time setup per book**. If a study-guide folder already exists for the book, do not run this skill - run `coursesmith-generate` instead.

## What this skill produces

A folder on disk that the user can open in any browser:

```
study-guide-{book-slug}/
├── index.html             # Roadmap landing page, links to every chapter
├── manifest.json          # Book metadata, paths, chapter list with page ranges
├── assets/
│   ├── styles.css
│   └── script.js
└── chapters/
    └── NN-chapter-slug/
        └── index.html     # Placeholder page (chapter not yet generated)
```

Every chapter starts as a clickable placeholder so the roadmap works from day one. `coursesmith-generate` overwrites placeholders with real chapter content over successive sessions.

## Core principles

The handful of rules that hold across init and generate:

- **Paraphrase, never reproduce.** Publisher copyright is respected: the output is paraphrased educational notes for personal study, not redistribution. (Applies to `coursesmith-generate`; init only writes scaffolding, no book content.)
- **Technical fidelity.** Code, commands, paths, version numbers, error strings are preserved verbatim.
- **No fabrication.** Do not invent chapters, page ranges, or table-of-contents entries that aren't in the source.
- **British English, no AI tells.** No em dashes. No "delve", "leverage" as a verb, "robust", "comprehensive", "navigate the complexities". Plain technical writing.

## Steps

### 1. Locate the source

The user gives a path to a `.pdf`, `.docx`, or `.epub`. If the prompt mentions a file by name only, ask for or infer the full path.

### 2. Decide the output folder

Default: the source file's parent directory, with the guide in a subfolder named `study-guide-{slug}`. For example, `~/books/black-hat-python.pdf` gives `~/books/study-guide-black-hat-python-3rd-ed/`.

If the user gave a different path in the prompt, use that. The folder need not exist yet; create it with `mkdir -p`.

The slug is lowercase, hyphenated, includes the edition if known: `black-hat-python-3rd-ed`, `the-linux-command-line-2nd-ed`.

### 3. Read the table of contents off disk

PDFs:

```bash
pdftotext -f 1 -l 25 "{source_pdf}" -
```

Adjust the page range if the ToC is further into the front matter. For docx use `pandoc -t plain` or read the file directly and split on chapter headings. For epub, unzip and read the `nav.xhtml` / `toc.ncx`.

From the ToC, derive each chapter's **1-based PDF page range**. PDF page numbers often differ from printed page numbers because of front matter. Spot-check by opening one chapter's first PDF page and confirming the title matches; if not, derive an offset (printed page X is PDF page X + offset) and apply it across the board.

If `pdftotext` is missing, install poppler-utils (`apt install poppler-utils`, `brew install poppler`). Acceptable substitutes: `pypdf`, `pdfplumber`. Use whatever is available.

### 4. Confirm the chapter list with the user

Show the proposed list with chapter numbers, titles, and PDF page ranges. Ask:

> Does this look right? Any chapters to merge, split, or skip before I build the scaffold?

Wait for confirmation. Adjust the list per the user's reply.

### 5. Write the scaffold

Create the folder structure and files in this order:

1. `mkdir -p {output_dir}/assets {output_dir}/chapters`
2. Copy `templates/styles.css` to `{output_dir}/assets/styles.css`
3. Copy `templates/script.js` to `{output_dir}/assets/script.js`
4. For each chapter, create `{output_dir}/chapters/NN-{chapter-slug}/` and write a `index.html` based on `templates/chapter-placeholder.html` with the chapter's metadata substituted.
5. Write `{output_dir}/manifest.json` from `templates/manifest.json`. All chapters get `status: "pending"`, `page_start` and `page_end` set, `subsection_count: 0`, `card_count: 0`, `lab_type: null`, `subsections: []`. Record `source_pdf` and `output_dir` as absolute paths. Set `generated_at` and `last_modified` to the current ISO 8601 timestamp.
6. Write `{output_dir}/index.html` from `templates/roadmap.html`. Render a roadmap card for every chapter (all "pending" at this point), linking to its placeholder page.

For `.docx` / `.epub` sources, set `page_start` and `page_end` to `0` in the manifest and note the source format in the `_format` field; `coursesmith-generate` will split by chapter heading instead of page range.

### 6. Tell the user the folder is ready

> Folder set up at `{output_dir}/`. Open `index.html` in a browser to see the roadmap. Generating chapter 1 now.

### 7. Hand off to coursesmith-generate

Invoke `coursesmith-generate` via the Skill tool to do chapter 1 in the same run, so the user's first prompt produces scaffold + chapter 1.

If the user explicitly asked for "setup only" or "don't do chapter 1 yet", skip this step and tell them: "Scaffold ready. Say 'do chapter 1' (or invoke coursesmith-generate) whenever you want to start."

## Bundled files

| File | Purpose |
|---|---|
| `templates/manifest.json` | Manifest schema with field comments |
| `templates/roadmap.html` | Roadmap landing page template |
| `templates/chapter-placeholder.html` | Placeholder page written for every chapter at init |
| `templates/styles.css` | Shared glassmorphic theme, copied into `assets/` |
| `templates/script.js` | Progress tracking and quiz logic, copied into `assets/` |
| `scripts/package_guide.py` | Zips the folder; used only for the claude.ai/Cowork fallback or on user request |
| `references/non-claude-code-fallback.md` | Zip-handover details for ephemeral environments |

## Running outside Claude Code

The skill assumes the user's filesystem persists between sessions. On claude.ai or Cowork without persistent storage, see `references/non-claude-code-fallback.md` - briefly, the folder is zipped to `/mnt/user-data/outputs/` at the end of the session and the user re-uploads the zip next time.

## What this skill never does

- Generate chapter content (paraphrasing, quizzes, code, Anki) - that lives in `coursesmith-generate`.
- Read the body of the book - init only reads the ToC pages.
- Overwrite an existing study-guide folder. If `{output_dir}/manifest.json` already exists, stop and tell the user: "A study guide already exists at `{output_dir}`. Use coursesmith-generate to add the next chapter or refine an existing one."
