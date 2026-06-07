---
name: coursesmith-init
description: One-time setup for a Coursesmith study guide. Reads a non-fiction book PDF off disk, extracts the table of contents, derives chapter page ranges, scaffolds a TryHackMe/HTB-Academy-style HTML course folder (manifest.json, roadmap index.html, styles, placeholder pages for every chapter), then hands off to coursesmith-generate for chapter 1. Use ONLY for the first run on a new book ("turn this book into a study guide", "start a course from this PDF", "make me a TryHackMe-style course from this book"). For every subsequent run (next chapter, refine, whole-book loop) use coursesmith-generate instead.
---

# Coursesmith - Init

Sets up the on-disk scaffold for an interactive course built from a non-fiction book, then hands off to `coursesmith-generate` to produce chapter 1.

This is **one-time setup per book**. If a study-guide folder already exists for the book, do not run this skill - run `coursesmith-generate` instead.

## What this skill produces

`study-guide-{book-slug}/` containing `index.html` (roadmap), `manifest.json`, `assets/{styles.css,script.js}`, and `chapters/NN-{slug}/index.html` placeholders for every chapter. Placeholders are clickable from day one; `coursesmith-generate` overwrites them with real content later.

## Core rule

**No fabrication.** Do not invent chapters, page ranges, or ToC entries that aren't in the source. (Paraphrasing rules don't apply here — init writes scaffolding, not book content.)

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

From the ToC, derive each chapter's **1-based PDF page range**. PDF page numbers often differ from printed page numbers because of front matter.

**Strip front matter.** Drop non-chapter entries that aren't study material: preface, foreword, introduction-to-the-book, acknowledgments, about-the-author, dedication, copyright. *Keep* numbered chapters and appendices (appendices are usually worth studying). When in doubt about a borderline entry, keep it — it's cheap to drop later and the list is printed for the user to see.

If `pdftotext` is missing, install poppler-utils (`apt install poppler-utils`, `brew install poppler`). Acceptable substitutes: `pypdf`, `pdfplumber`. Use whatever is available.

### 4. Verify the page offset (the real correctness guard)

The page offset is the dangerous part of init: a wrong offset silently poisons `page_start`/`page_end` for **every** chapter in the manifest, and `coursesmith-generate` reads those ranges for the whole book afterwards. A wrong chapter *title* only affects a cheap-to-redo folder name; a wrong *offset* corrupts every future chapter. So the guard goes here, on the offset — not on a human eyeballing the title list.

Run an **automated spot-check** (PDF sources only):

1. Open the first PDF page of **chapter 1** (`pdftotext -f {ch1_start} -l {ch1_start} "{source_pdf}" -`) and confirm the chapter title appears near the top.
2. Open the first PDF page of the **last chapter** and confirm the same. (Checking both ends catches offset drift that a single check would miss.)

If either title matches its page → the offset is good. **Print the final chapter list to chat** (numbers, titles, PDF page ranges) so the user can see what was derived, then proceed automatically to step 5 — no pause, no "does this look right?".

If a title doesn't match → derive the offset (printed page X is PDF page X + offset), apply it across the board, and re-run the spot-check. If it then matches, proceed automatically.

**Pause only if the spot-check still can't be confirmed after deriving an offset** — this is the one case worth a human. Show the proposed list (numbers, titles, PDF page ranges) and the mismatch, and ask:

> I couldn't confirm the PDF page offset automatically — chapter {N}'s title didn't appear on its expected page. Here's the list I derived: {list}. Does this look right, or what's the correct offset?

Adjust per the reply.

For `.docx`/`.epub` there are no PDF page numbers to verify — skip the spot-check and proceed.

#### The `--step` flag

If the user's prompt includes `--step` (or asks to "review the chapters", "let me check the list first", etc.), **always** print the full list and pause for confirmation before building the scaffold, regardless of whether the spot-check passed:

> Here's the chapter list with PDF page ranges: {list}. Any chapters to merge, split, or skip before I build the scaffold?

Wait for confirmation and adjust per the reply. Without `--step`, the default is autonomous: print the list for transparency, but only pause if the spot-check failed (above).

### 5. Convert the PDF to markdown (PDF sources only)

Before writing the scaffold, convert the entire PDF to a single markdown file with embedded page-number markers. This happens once so `coursesmith-generate` can slice chapters from it directly without re-spawning a JVM each session.

First ensure the output directory exists, then convert:

```python
import subprocess, os, glob as _glob

# Ensure Java 11+ is on PATH — systems often have a Java 8 stub that shadows newer installs.
def _find_java_home():
    # Honour an already-correct JAVA_HOME
    jh = os.environ.get("JAVA_HOME", "")
    if jh:
        try:
            out = subprocess.check_output(
                [os.path.join(jh, "bin", "java"), "-version"],
                stderr=subprocess.STDOUT, text=True)
            major = out.split('"')[1].split(".")
            ver = int(major[1]) if major[0] == "1" else int(major[0])
            if ver >= 11:
                return jh
        except Exception:
            pass
    # Search common install locations (newest version sorts last with reverse=True)
    patterns = [
        r"C:\Program Files\Eclipse Adoptium\jdk-*",
        r"C:\Program Files\Microsoft\jdk-*",
        r"C:\Program Files\Java\jdk-*",
        r"C:\Program Files\BellSoft\LibericaJDK-*",
        "/usr/lib/jvm/temurin-*",
        "/usr/lib/jvm/java-*-openjdk*",
    ]
    candidates = []
    for p in patterns:
        candidates.extend(_glob.glob(p))
    for c in sorted(candidates, reverse=True):
        java_bin = os.path.join(c, "bin", "java") + (".exe" if os.name == "nt" else "")
        if os.path.exists(java_bin):
            return c
    return None

_jh = _find_java_home()
if _jh:
    os.environ["JAVA_HOME"] = _jh
    os.environ["PATH"] = os.path.join(_jh, "bin") + os.pathsep + os.environ["PATH"]

try:
    import opendataloader_pdf
    os.makedirs("{output_dir}", exist_ok=True)
    opendataloader_pdf.convert(
        input_path=["{source_pdf}"],
        output_dir="{output_dir}",
        format="markdown",
        markdown_page_separator="\n\n<!-- Page %page-number% -->\n\n",
        image_output="off",
        quiet=True,
    )
    # Library writes {pdf_stem}.md — rename to source.md for consistency
    pdf_stem = os.path.splitext(os.path.basename("{source_pdf}"))[0]
    os.rename(
        os.path.join("{output_dir}", pdf_stem + ".md"),
        os.path.join("{output_dir}", "source.md"),
    )
    source_md = os.path.join("{output_dir}", "source.md")
except (FileNotFoundError, subprocess.CalledProcessError, ImportError) as e:
    source_md = None
```

**If conversion fails**, tell the user and continue — init is not blocked:

> Could not convert PDF to markdown (`{error}`). Chapter generation will fall back to `pdftotext`/`pypdf` per chapter. To enable one-time conversion, install Java 11+ from https://adoptium.net.

Set `source_md: null` in the manifest. `coursesmith-generate` handles the fallback automatically.

**Skip this step entirely** for `.docx` and `.epub` sources — set `source_md: null`.

### 6. Write the scaffold

Create the folder structure and files in this order:

1. `mkdir -p {output_dir}/assets {output_dir}/chapters`
2. Copy `templates/styles.css` to `{output_dir}/assets/styles.css`
3. Copy `templates/script.js` to `{output_dir}/assets/script.js`
4. For each chapter, create `{output_dir}/chapters/NN-{chapter-slug}/` and write a `index.html` based on `templates/chapter-placeholder.html` with the chapter's metadata substituted.
5. Write `{output_dir}/manifest.json` from `templates/manifest.json`. All chapters get `status: "pending"`, `page_start` and `page_end` set, `subsection_count: 0`, `card_count: 0`, `lab_type: null`, `subsections: []`. Record `source_pdf`, `output_dir`, and `source_md` as absolute paths (`source_md` is null if conversion failed or source is not a PDF). Set `generated_at` and `last_modified` to the current ISO 8601 timestamp.
6. Write `{output_dir}/index.html` from `templates/roadmap.html`. Render a roadmap card for every chapter (all "pending" at this point), linking to its placeholder page.

For `.docx` / `.epub` sources, set `page_start` and `page_end` to `0` in the manifest and note the source format in the `_format` field; `coursesmith-generate` will split by chapter heading instead of page range.

### 7. Tell the user the folder is ready

> Folder set up at `{output_dir}/`. Open `index.html` in a browser to see the roadmap. Generating chapter 1 now.

### 8. Hand off to coursesmith-generate

Invoke `coursesmith-generate` immediately after step 6, no confirmation prompt — the handoff is part of the contract. **Exception:** if the user's original prompt said "setup only", "scaffold only", or "don't do chapter 1 yet", stop instead and tell them: "Scaffold ready. Say 'do chapter 1' whenever you want to start." A neutral prompt ("build a course from this PDF") is not an opt-out.

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
- Read the body of the book for content - init reads the ToC pages plus the first page of the first and last chapters to verify the page offset (step 4). It never reads chapters in full or extracts content; that lives in `coursesmith-generate`.
- Overwrite an existing study-guide folder. If `{output_dir}/manifest.json` already exists, stop and tell the user: "A study guide already exists at `{output_dir}`. Use coursesmith-generate to add the next chapter or refine an existing one."
