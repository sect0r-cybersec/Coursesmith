---
name: coursesmith-generate
description: Generates content into an existing Coursesmith study-guide folder. Use for every run after the first one - "next chapter", "carry on the course", "do chapter 5", "do all the remaining chapters now", or refine requests like "the quiz for chapter 3 is too easy", "rewrite chapter 2's notes more concisely", "the lab for chapter 7 should use Docker". Reads manifest.json from the existing folder, extracts the target chapter's pages from the source PDF, paraphrases subsections, builds embedded quizzes, extracts code examples, decides a lab type, and generates a 15-30 card Anki cloze deck. Requires a folder already set up by coursesmith-init; if no manifest is found, stop and tell the user to run coursesmith-init first.
---

# Coursesmith - Generate

Produces chapter content (or refines existing content) inside a study-guide folder that `coursesmith-init` has already scaffolded. This is the **repeat action** - run it every session after the first.

## Preconditions

Before doing anything else: look for `manifest.json` in the folder the user named (or referenced). If no manifest exists, stop and tell the user:

> No study guide folder found here. Run `coursesmith-init` first to set one up for this book.

Do not try to scaffold a folder yourself. That's `coursesmith-init`'s job.

## Modes

Pick a mode from what the user said:

- **Next chapter** (default): user said "next chapter", "carry on", or named no chapter. Generate the lowest-numbered chapter still `pending`.
- **Named chapter**: user named a chapter ("do chapter 5", "chapter 3 please"). Generate that one.
- **Refine**: user wants to tweak an existing chapter ("the quiz for chapter 3 is too easy", "add more cards for chapter 5", "the lab for chapter 7 should use Docker", "rewrite chapter 2's notes more concisely"). Regenerate only the affected component, leave the rest alone.
- **Loop the rest**: user explicitly asked to do everything remaining ("do all the chapters now", "generate the whole thing in one go"). Loop the per-chapter flow over every remaining `pending` chapter. Warn first about context pressure on long books; if context runs tight, stop cleanly with the folder consistent and tell the user "I got through chapter N; say 'next chapter' in a fresh session to carry on from N+1."

The default action is **next chapter**.

## Core principles

These are non-negotiable for every chunk of generated content:

- **Paraphrase, never reproduce.** Publishers (No Starch, O'Reilly, Manning, etc.) hold copyright. Output is paraphrased educational notes for the user's personal study, not redistribution. Never reproduce long verbatim passages. Aim for 40-60% of the original length on prose-heavy chapters. See `references/paraphrasing-rules.md` for what to cut, keep, and paraphrase, with worked examples. Read it before generating the first chapter.
- **Technical fidelity is non-negotiable.** Paraphrase prose. Do not paraphrase: command syntax, code, exact error messages, file paths, registry keys, API names, version numbers, configuration values, or anything where the wording *is* the technical content. If condensing risks losing a detail, keep the detail.
- **No fabrication.** Do not invent or extrapolate beyond the source. If the source is ambiguous, preserve the ambiguity. Do not add information that isn't there, even if it would be technically correct.
- **British English, no AI tells.** No em dashes. No emojis unless the source uses them. No "delve", "leverage" (verb), "robust", "comprehensive", "navigate the complexities", "in today's fast-paced world", "it's important to note". Plain technical writing, matching the source's voice where possible.

## Reading the chapter off disk

Read only what this chapter needs. Never load the whole book.

For PDFs, extract the chapter's pages using its stored range:

```bash
pdftotext -f {page_start} -l {page_end} "{source_pdf}" -
```

For code- or figure-heavy chapters where layout matters, add `-layout` to preserve columns and indentation. For embedded images the user needs:

```bash
pdfimages -f {page_start} -l {page_end} -png "{source_pdf}" {output_dir}/chapters/NN-slug/images/img
```

For `.docx` / `.epub` sources (manifest shows `page_start: 0`), split by chapter heading and read just that chapter's range.

If `pdftotext` is missing, install poppler-utils, or fall back to `pypdf` / `pdfplumber`.

## Per-chapter flow (next-chapter and named-chapter modes)

1. Read `manifest.json` to get `source_pdf`, `output_dir`, and the chapter list.
2. Pick the target chapter (lowest pending, or the named one).
3. Extract the chapter's pages off disk using the stored `page_start`/`page_end`.
4. Identify the chapter's subsections from the extracted text. Aim for 3-7 subsections per chapter; group finer sub-subsections sensibly.
5. For each subsection: paraphrase the prose (rules in `references/paraphrasing-rules.md`), preserve technical content verbatim, write a 3-5 question quiz at the end.
6. Extract code examples. Inline them as syntax-highlighted blocks in the notes (Prism.js classes: `language-python`, `language-bash`, etc.) and also write each as a standalone file in `{chapter_dir}/code-examples/NN-description.{ext}` with the source's comments preserved. After writing the files, render a styled directory page so the user doesn't see the browser's raw directory listing:

   ```bash
   python {coursesmith-generate-skill-dir}/scripts/render_code_index.py \
     --dir {chapter_dir}/code-examples \
     --book-title "{Book Title}" \
     --chapter-num {N} \
     --chapter-title "{Chapter Title}"
   ```

   If the chapter has no code examples, skip this step entirely (don't create an empty `code-examples/`).
7. Decide the lab type using `references/lab-decisions.md`. Generate `lab.ipynb` (from `templates/lab.ipynb`) or `lab-guide.md` (from `templates/lab-guide.md`), or skip the lab entirely for purely conceptual chapters and note "Conceptual chapter, no hands-on lab" in the chapter intro.

   For markdown-based labs (`lab-guide.md`), render a styled sibling `lab.html` so the lab page matches the rest of the course theme. Keep the markdown source alongside it for users who want to download or edit it:

   ```bash
   python {coursesmith-generate-skill-dir}/scripts/render_lab.py \
     --input  {chapter_dir}/lab-guide.md \
     --output {chapter_dir}/lab.html \
     --book-title "{Book Title}" \
     --chapter-num {N} \
     --chapter-title "{Chapter Title}"
   ```

   The chapter's lab resource card (step 9) should point at `lab.html`, not `lab-guide.md`. Jupyter labs (`lab.ipynb`) are not rendered to HTML; their resource card stays as a `download` link.
8. **Ask the user before generating Anki cards.** Cards take time and are not everyone's review style, so default to no:

   ```
   AskUserQuestion: "Generate an Anki flashcard deck for this chapter?"
     - Option 1 (highlighted as Recommended): "No, skip Anki" - default
     - Option 2: "Yes, generate cards"
   ```

   If the user picks **No**: skip card generation, set `card_count: 0` in the manifest, and omit the Anki resource card from the chapter HTML. Move straight to step 9.

   If the user picks **Yes**: generate 15-30 cloze cards using `references/anki-card-rules.md`, write them to a temporary `cards.json`, then:

   ```bash
   python {coursesmith-generate-skill-dir}/scripts/generate_anki.py \
     --cards cards.json \
     --deck-name "{Book Title} :: Chapter {N}: {Chapter Title}" \
     --output {chapter_dir}/anki-deck.apkg
   ```

   Delete `cards.json` after the deck is built.

   In **loop mode** (see below), ask once per chapter the same way; the user can hit the same default each time, or change their mind for a denser chapter.
9. Render the chapter `index.html` from `templates/chapter.html`, substituting the chapter content, subsections, code blocks, quiz blocks, resource cards, and sidebar links. Resource cards to render:

   - **Anki Deck card** only if Anki was generated for this chapter (`card_count > 0`).
   - **Lab card** points at `lab.html` for markdown labs, `lab.ipynb` for Jupyter labs, omitted for conceptual chapters.
   - **Code Examples card** points at `code-examples/index.html` (the rendered listing), not the raw directory, and is omitted if the chapter has no code.
10. Write the chapter into its folder, overwriting the placeholder created by init.
11. Update `manifest.json` for this chapter: `status: "ready"`, fill in `subsection_count`, `card_count` (0 if user declined Anki), `lab_type`, and `subsections` (each `{id, title}`), set `last_modified` to the current ISO 8601 timestamp.
12. Re-render the roadmap `index.html` from the manifest so the chapter shows as ready.
13. Tell the user the chapter is done and which is next, e.g.:

    > Chapter 3 is done, written to `{output_dir}`. Open `index.html` in your browser to see it on the roadmap. Next pending chapter is 4 - say "next chapter" when you want it.

    On the very first chapter, also tell them: "Progress (subsection ticks, quiz answers) is saved in your browser's localStorage, so you can close the tab and come back."

    **If the chapter just generated is the last `pending` chapter** (every chapter now `status: "ready"`), replace the "next chapter" line with:

    > Chapter {N} is done - that's the last one. Every chapter is now ready. Run `coursesmith-cert` whenever you want your certificate of completion.

    In loop mode (see below), the same hint fires once at the end of the loop instead of after each chapter.

## Refine mode

The user wants to change one component of an already-generated chapter. Regenerate only that component; leave the rest alone.

Mapping:

| User asks for | Regenerate |
|---|---|
| "quizzes too easy" / "more challenging quiz" | the affected subsection quiz block(s) inside `{chapter_dir}/index.html` |
| "more cards" / "different cards" | `anki-deck.apkg`, update `card_count` in manifest |
| "lab should use Docker" / "different lab" | `lab.ipynb` or `lab-guide.md`, update `lab_type` if it changed |
| "rewrite notes more concisely" / "more detail on X" | the subsection bodies in `{chapter_dir}/index.html` |
| "fix code example NN" | the file in `{chapter_dir}/code-examples/` and the inline copy in `index.html` |

After regenerating, update `manifest.json` with a new `last_modified` timestamp on that chapter. Do not re-render the roadmap unless `status` changed.

## Loop mode

The user explicitly asked for the whole remainder ("do all the chapters now"). Before starting, warn:

> This is a long book ({N} remaining chapters). Doing it all at once may run the context tight before the end. If it does, I'll stop cleanly and you can pick up with "next chapter" in a fresh session - the folder keeps everything done so far.

Then loop the per-chapter flow over every `pending` chapter in order, updating the manifest and roadmap after each. Because every chapter is written to disk before moving on, an interruption leaves a consistent partial folder.

If context runs tight mid-loop, stop cleanly, leave the manifest consistent, and tell the user where you stopped.

## File structure (reference)

The on-disk layout after several runs:

```
study-guide-{book-slug}/
├── index.html                     # Roadmap; re-rendered after every chapter
├── manifest.json                  # Updated after every chapter
├── assets/
│   ├── styles.css
│   └── script.js
└── chapters/
    └── NN-chapter-slug/           # NN zero-padded
        ├── index.html             # Real content (or placeholder if not yet done)
        ├── anki-deck.apkg
        ├── code-examples/         # Only if chapter has code
        │   ├── 01-hello.py
        │   └── ...
        ├── lab.ipynb              # Or lab-guide.md, or neither
        └── lab-guide.md
```

A chapter has `lab.ipynb` OR `lab-guide.md` OR neither - never both.

## Working with code in the source

1. **Inline in notes:** wrap in `<pre><code class="language-X">...</code></pre>` so Prism.js highlights it. The `script.js` from init adds a Copy button automatically. Below the inline block, link to the standalone file: `<a class="code-fullfile-link" href="code-examples/NN-name.ext">View full file</a>`.
2. **Standalone in `code-examples/`:** write the full file, preserve the source author's comments, variable names, and structure exactly. Name files `NN-description.ext`, numbered in source order.
3. **Do not refactor, modernise, or improve the source's code.** The user is learning from this book; their mental model needs to match what's on the page. If the source's code is buggy, preserve the bug verbatim and add a small `<div class="note warning">` flagging it.

## Quiz format

Each subsection ends with a `<details class="quiz-block">` containing 3-5 questions. Two question types:

- **MCQ**: `<div class="quiz-question" data-type="mcq" data-correct="b">` with 4 options as `<label class="quiz-option" data-value="a|b|c|d">`. One correct. Always include a brief `<div class="quiz-explanation">` revealed on submit.
- **Short answer**: `<div class="quiz-question" data-type="short">` with a text input. The model answer is revealed on "Show model answer".

All answers are embedded in the HTML; the user grades themselves for short-answer. No backend. The exact markup is in `templates/chapter.html`.

## Anki cards

Read `references/anki-card-rules.md` for what to clozify (definitions, command syntax, defaults, IDs, function signatures) and what to skip (long prose, conceptual paragraphs without a discrete fact). 15-30 cards per chapter, scaled to chapter density - don't pad.

The `scripts/generate_anki.py` script takes a JSON list of cards (each `{text, extra}`) plus a deck name and writes the `.apkg`. The script auto-installs `genanki` if missing.

## Bundled files

| File | Purpose |
|---|---|
| `templates/chapter.html` | Chapter notes page template (real content) |
| `templates/lab.ipynb` | Jupyter notebook lab template |
| `templates/lab-guide.md` | Markdown lab guide template (non-Python labs) |
| `scripts/generate_anki.py` | genanki wrapper for cloze decks (only used if the user opts in) |
| `scripts/render_lab.py` | Renders `lab-guide.md` to a styled `lab.html` matching the course theme |
| `scripts/render_code_index.py` | Renders `code-examples/index.html` listing every script with the course theme |
| `references/paraphrasing-rules.md` | Detailed paraphrasing guidance with worked example |
| `references/lab-decisions.md` | Lab type decision rules per content type |
| `references/anki-card-rules.md` | What to clozify, formatting, volume guidance |

The `package_guide.py` zip script lives in `coursesmith-init`. If the user explicitly asks for a zip backup, use it from there:

```bash
python {coursesmith-init-skill-dir}/scripts/package_guide.py \
  --source {output_dir} \
  --output {output_dir}.zip
```

For running outside Claude Code, see `references/non-claude-code-fallback.md` in `coursesmith-init`.

## When things go wrong

- **OCR'd PDF is gibberish for this chapter:** stop. Tell the user. Don't generate notes from broken text.
- **Chapter is too long for one turn:** split it into halves. Generate the first half, then continue the second half in the next turn. Make the split visible (clear subsection headings).
- **Source uses outdated tooling (e.g. Python 2):** preserve the source's code verbatim, but add a one-line `<div class="note">` in the chapter intro noting the version mismatch and what differs in modern equivalents. Don't silently modernise.
- **Context runs out mid-loop (loop mode):** stop cleanly. The folder on disk holds every chapter done so far. Tell the user where you stopped and how to resume.

## Output checklist (per chapter)

Before declaring a chapter done, verify:

- [ ] Chapter `index.html` written and renders without errors
- [ ] All subsections have quizzes (3-5 questions each)
- [ ] Code examples extracted to `code-examples/` and linked from notes
- [ ] `code-examples/index.html` rendered by `render_code_index.py` (if the chapter has code)
- [ ] Lab file produced (or chapter explicitly marked as conceptual-only)
- [ ] For markdown labs: `lab.html` rendered by `render_lab.py` alongside the `.md` source
- [ ] User was asked about Anki; deck generated only if they opted in (15-30 valid cloze cards)
- [ ] `manifest.json` updated (`status: "ready"`, counts, `last_modified`)
- [ ] Roadmap `index.html` re-rendered
- [ ] No em dashes, no emojis (unless source-driven), British English throughout
- [ ] No verbatim long passages from source
- [ ] Technical specifics (code, commands, paths, IDs) preserved verbatim
- [ ] Chapter written into `output_dir` on disk, alongside existing chapters
