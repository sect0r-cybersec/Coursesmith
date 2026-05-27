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
- **Teach the subject, don't narrate the chapter.** The grammatical subject of your sentences should be the thing being taught (Bash, TCP, the handshake), not the document ("this chapter", "the book", "we will cover"). No previews of structure, no "everything later builds on this" scaffolding, no lists of upcoming section headings dressed up as prose. The reader is here to learn the topic, not to be told what the chapter contains. See the intro worked example in `references/paraphrasing-rules.md`.
- **British English, no AI tells.** Full no-go list in `references/paraphrasing-rules.md`. Plain technical writing, match the source's voice.

## Reading the chapter off disk

Read only this chapter's range, never the whole book. PDFs: `pdftotext -f {page_start} -l {page_end} "{source_pdf}" -` (add `-layout` for code/figure-heavy chapters). For embedded images: `pdfimages -f {page_start} -l {page_end} -png "{source_pdf}" {chapter_dir}/images/img`. For `.docx` / `.epub` (manifest shows `page_start: 0`), split by heading. Fallback if `pdftotext` is missing: `pypdf` or `pdfplumber`.

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
8. **Ask before generating Anki.** AskUserQuestion: "Generate an Anki flashcard deck for this chapter?" — `"No, skip Anki"` (Recommended, default) / `"Yes, generate cards"`.

   - **No:** `card_count: 0`, omit the Anki resource card, go to step 9.
   - **Yes:** generate 15-30 cloze cards per `references/anki-card-rules.md`, write `cards.json`, run `python {coursesmith-generate-skill-dir}/scripts/generate_anki.py --cards cards.json --deck-name "{Book Title} :: Chapter {N}: {Chapter Title}" --output {chapter_dir}/anki-deck.apkg`, delete `cards.json`.

   In loop mode, ask once per chapter (the user can change their mind for denser chapters).
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

Per chapter folder (`chapters/NN-{slug}/`): `index.html`, optional `anki-deck.apkg`, optional `code-examples/NN-*.ext` (only if chapter has code), and exactly one of `lab.ipynb` / `lab-guide.md` / neither.

## Working with code in the source

- **Inline:** `<pre><code class="language-X">...</code></pre>` (Prism.js highlights; init's `script.js` adds a Copy button). Below the block, link to the standalone file: `<a class="code-fullfile-link" href="code-examples/NN-name.ext">View full file</a>`.
- **Standalone:** write the full file under `code-examples/NN-description.ext`, source's comments / names / structure preserved exactly, numbered in source order.
- **Never refactor, modernise, or fix the source's code.** The user's mental model must match the page. If the source's code is buggy, preserve the bug and add a `<div class="note warning">` flagging it.

## Quiz format

Each subsection ends with a `<details class="quiz-block">` containing 3-5 questions. Two question types:

- **MCQ**: `<div class="quiz-question" data-type="mcq" data-correct="b">` with 4 options as `<label class="quiz-option" data-value="a|b|c|d">`. One correct. Always include a brief `<div class="quiz-explanation">` revealed on submit.
- **Short answer**: `<div class="quiz-question" data-type="short">` with a text input. The model answer is revealed on "Show model answer".

All answers are embedded in the HTML; the user grades themselves for short-answer. No backend. The exact markup is in `templates/chapter.html`.

## Anki cards

15-30 cards per chapter (scaled to density, don't pad). Rules in `references/anki-card-rules.md`. `scripts/generate_anki.py` takes `{text, extra}` JSON + deck name, auto-installs `genanki` if missing.

## Bundled files

- `templates/`: `chapter.html`, `lab.ipynb`, `lab-guide.md`
- `scripts/`: `generate_anki.py`, `render_lab.py`, `render_code_index.py`
- `references/`: `paraphrasing-rules.md`, `lab-decisions.md`, `anki-card-rules.md`

Zip backups: use `coursesmith-init/scripts/package_guide.py`. Ephemeral environments: `coursesmith-init/references/non-claude-code-fallback.md`.

## When things go wrong

- **OCR'd PDF is gibberish:** stop. Tell the user. Don't generate notes from broken text.
- **Chapter too long for one turn:** split into halves with visible subsection-heading splits; continue in the next turn.
- **Outdated tooling in source (e.g. Python 2):** preserve code verbatim, add a one-line `<div class="note">` in the intro flagging the version and what differs today. Don't silently modernise.
- **Context tight mid-loop:** stop cleanly; folder on disk is consistent. Tell the user where to resume.

## Output checklist (per chapter)

- [ ] Subsections each have a 3-5 question quiz
- [ ] Code extracted to `code-examples/` + inline blocks linked; `code-examples/index.html` rendered (if any code)
- [ ] Lab produced (or chapter marked conceptual-only); markdown labs have `lab.html` rendered alongside the `.md`
- [ ] Anki: user asked, deck generated only if opted in
- [ ] `manifest.json` and roadmap re-rendered
- [ ] No em dashes / no AI tells; technical specifics (code, commands, paths, IDs) verbatim; no long verbatim prose
