# Coursesmith

Claude Code skills that turn a non-fiction book PDF into a self-contained, browser-openable interactive study guide — with quizzes, labs, Anki cards, and a certificate of completion.

## Skills

### `coursesmith-init`
One-time setup for a new book. Reads the PDF, extracts the table of contents, derives chapter page ranges, and scaffolds a TryHackMe/HTB-Academy-style course folder with a roadmap index, placeholder chapter pages, styles, and `manifest.json`. Hands off to `coursesmith-generate` for chapter 1 automatically.

Run this once per book.

### `coursesmith-generate`
Generates (or refines) chapter content inside an existing study-guide folder. Per chapter it produces:
- Paraphrased study notes (40–60% of source length)
- Embedded multiple-choice and code-completion quizzes
- A hands-on lab (shell, Python, Docker, or CTF-style depending on the chapter)
- A 15–30 card Anki cloze deck

Modes: next chapter (default), named chapter, refine a component, or loop all remaining chapters.

Requires a folder already set up by `coursesmith-init`.

### `coursesmith-cert`
Generates a personalised PNG certificate of completion once every chapter is marked ready. Auto-derives a neon accent colour from the book's cover, extracts the author from PDF metadata, and renders via headless Chromium. Writes `certificate.png` into the study-guide folder and links it from the roadmap.

## Output structure

```
study-guide-{book-slug}/
├── index.html                  # Roadmap landing page
├── manifest.json               # Book metadata, chapter list, status tracking
├── assets/
│   ├── styles.css
│   └── script.js
├── chapters/
│   └── NN-chapter-slug/
│       ├── index.html          # Chapter notes + quizzes
│       └── lab/
│           └── lab-guide.md
└── certificate.png             # Generated after all chapters complete
```

## Usage

Install the skills via the Claude Code skill installer, then in any Claude Code session:

```
/coursesmith-init path/to/book.pdf
/coursesmith-generate
/coursesmith-generate chapter 5
/coursesmith-cert
```

## Requirements

- Claude Code with skill support
- Python 3.9+ (scripts auto-install their own dependencies)
- `pdftotext` / `pdfimages` (poppler-utils)
- Chromium (auto-installed by Playwright on first cert render)
