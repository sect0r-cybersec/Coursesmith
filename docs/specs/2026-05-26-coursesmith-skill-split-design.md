# Coursesmith: splitting book-to-study-guide into two skills

**Date:** 2026-05-26
**Status:** Approved (brainstorming)
**Supersedes structure of:** `~/.claude/skills/book-to-study-guide/`

## Motivation

The current `book-to-study-guide` SKILL.md is ~320 lines covering four operating modes (init, generate chapter, refine, whole-book loop). It is long enough that Claude misses or under-weights instructions when following it end to end. The driver for this split is followability: each new SKILL.md should be short enough to be read and acted on reliably in a single turn.

The current name is also generic and undersells the output (it produces an interactive course with labs and Anki decks, not just a "study guide"). The new family name is `coursesmith`, evoking craft and transformation.

## Outcome

Two skills replace the single existing one:

- `coursesmith-init` — one-time per book. Sets up the scaffold and generates chapter 1.
- `coursesmith-generate` — every subsequent run. Generates the next chapter, refines an existing chapter, or loops through the rest of the book.

The combined behaviour is identical to what the existing skill does today; only the packaging changes.

## Boundary

The split is drawn at **what runs once per book** vs **what runs once per chapter (and may repeat)**.

### coursesmith-init

**Triggers:** "turn this book into a study guide", "start a course from this PDF", "make me a course out of this book", and similar first-run phrases. The description states explicitly: *use this only the first time for a new book; for next-chapter or refine work use coursesmith-generate*.

**Responsibilities:**

1. Locate the source PDF on disk.
2. Decide the output folder (default: PDF's parent + `study-guide-{slug}`; user override honoured).
3. Read the ToC off disk (`pdftotext` on the first 10-30 pages) and derive each chapter's PDF page range.
4. Confirm the chapter list with the user.
5. Write `manifest.json` (all chapters `pending`, with `page_start`/`page_end`, `source_pdf`, `output_dir`).
6. Create the directory scaffold (`assets/`, `chapters/`).
7. Copy `styles.css` and `script.js` into `assets/`.
8. Write a placeholder page for every chapter so the roadmap is fully clickable from day one.
9. Generate the roadmap `index.html`.
10. Hand off to `coursesmith-generate` for chapter 1 via the Skill tool, so the user's first prompt still produces scaffold + chapter 1 in one run.

**Bundled files:**

- `templates/roadmap.html`
- `templates/chapter-placeholder.html`
- `templates/manifest.json`
- `templates/styles.css`
- `templates/script.js`
- `scripts/package_guide.py` (used by the claude.ai/Cowork fallback)
- `references/non-claude-code-fallback.md` (claude.ai zip-handover details, kept out of the main SKILL.md to keep it short)

**Expected SKILL.md size:** 80-120 lines.

### coursesmith-generate

**Triggers:** "next chapter", "carry on", "do chapter 5", "do all the remaining chapters now", "the quiz for chapter 3 is too easy", "rewrite chapter 2's notes more concisely", and similar repeat or refine phrases. The description states explicitly: *requires a study-guide folder already set up by coursesmith-init; if no manifest is found, stop and point the user at coursesmith-init*.

**Responsibilities:**

1. Read `manifest.json` to get `source_pdf`, `output_dir`, and the chapter list.
2. Pick the target chapter: the one the user named, or the lowest-numbered `pending` chapter.
3. Extract that chapter's pages off disk using its stored page range.
4. Run the per-chapter generation flow: paraphrase subsections, build 3-5-question subsection quizzes, extract code examples, decide lab type, generate 15-30 Anki cloze cards.
5. Write the chapter into its folder, overwriting the placeholder.
6. Update `manifest.json` (`status: ready`, fill in subsection/card/lab fields, `last_modified`).
7. Re-render the roadmap so the chapter shows as ready.
8. Tell the user the chapter is done and which is next.

Also handles:

- **Refine** (Mode 2 today): regenerate one component of an existing chapter only; touch only that component and `last_modified`.
- **Loop** (Mode 3 today): if the user explicitly asks for the whole remainder, loop the per-chapter flow with the existing context-pressure warning. On interruption, the folder is left consistent and the user resumes with "next chapter".

**Bundled files:**

- `templates/chapter.html`
- `templates/lab.ipynb`
- `templates/lab-guide.md`
- `scripts/generate_anki.py`
- `references/paraphrasing-rules.md`
- `references/lab-decisions.md`
- `references/anki-card-rules.md`

**Expected SKILL.md size:** 120-180 lines.

## Shared concerns

**Style rules.** Both skills produce user-visible text. The British-English / no-em-dash / no-AI-tells rules appear as a short paragraph in each SKILL.md rather than being deferred to a shared file, because they are short and load-bearing for every chunk of output.

**claude.ai / Cowork fallback.** Both skills mention the fallback in one or two sentences; full zip-handover details live in `references/non-claude-code-fallback.md` inside `coursesmith-init`. `coursesmith-generate` references this file by path when the user is running outside Claude Code and needs to package output at the end of each session.

**`package_guide.py`.** Lives in `coursesmith-init` only. `coursesmith-generate` references its path inside the init skill folder when the user explicitly asks for a zip. The script is small and rarely needed, so a single source of truth is preferable to duplication.

**Manifest as source of truth.** Unchanged. Both skills read and write `manifest.json` in `output_dir`. The init skill creates it; the generate skill mutates it.

## Hand-off on first run

When `coursesmith-init` finishes the scaffold, it invokes `coursesmith-generate` via the Skill tool to do chapter 1 in the same run. This preserves today's UX where a single first prompt produces a working folder plus chapter 1.

The init SKILL.md ends with an explicit instruction to invoke the generate skill, with a fallback message for the user if the invocation fails: "scaffold ready, say 'do chapter 1' or invoke coursesmith-generate to start."

## What does not change

- The on-disk file structure of the study guide (`index.html`, `manifest.json`, `assets/`, `chapters/NN-slug/...`).
- The output style (TryHackMe / HTB Academy aesthetic, dark glassmorphic).
- The per-chapter output (paraphrased notes, syntax-highlighted code, subsection quizzes, Anki deck, optional lab).
- The reading-off-disk strategy (one chapter's page range at a time via `pdftotext`).
- The four core principles (paraphrase never reproduce, technical fidelity, no fabrication, one chapter per sitting).

A user who already has a partially-built study guide from the old skill can continue with `coursesmith-generate` against the same folder; the manifest format is unchanged.

## Naming rationale

`coursesmith` reframes the output as a course rather than a study guide, and the `-smith` suffix evokes craft. The two suffixes `-init` and `-generate` describe lifecycle position rather than the unit of output: `init` is one-time setup, `generate` covers any production action (next chapter, refine, loop).

## Migration

The existing `book-to-study-guide` skill folder is left in place during transition. Two new sibling folders are created:

- `~/.claude/skills/coursesmith-init/`
- `~/.claude/skills/coursesmith-generate/`

Templates, scripts, and references are split between the two as listed above. Once both new skills are verified to work end-to-end on a fresh book, the old `book-to-study-guide` folder (and the `-cc` variant) can be removed.

## Out of scope

- Changing the output format, aesthetic, or per-chapter content rules.
- Adding new content types (e.g. video, audio, flashcards beyond Anki).
- Supporting non-book inputs (papers, blog posts, video transcripts).
- Any new functionality beyond what the existing skill already does.

This is a packaging refactor. Functional changes belong in a separate spec.
