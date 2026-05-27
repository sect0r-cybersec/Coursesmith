#!/usr/bin/env python3
"""Render a chapter's source file (chapter.yaml) into the chapter's index.html.

The model writes a compact YAML source instead of full HTML. This script expands
shortcodes, converts markdown bodies, renders quizzes, assembles the sidebar
from manifest.json, and writes the final page. Saves roughly 70% of the tokens
the model would otherwise spend on hand-written HTML.

Usage:
    python render_chapter.py \\
        --source   /path/to/chapters/NN-slug/chapter.yaml \\
        --manifest /path/to/manifest.json \\
        --output   /path/to/chapters/NN-slug/index.html

Auto-installs `pyyaml` and `markdown` if missing.

See templates/chapter.yaml for the source schema.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _ensure_deps():
    missing = []
    try:
        import yaml  # noqa: F401
    except ImportError:
        missing.append("pyyaml")
    try:
        import markdown  # noqa: F401
    except ImportError:
        missing.append("markdown")
    if missing:
        print(f"installing missing deps: {missing}", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing]
        )


# ----- Shortcode definitions --------------------------------------------------

# Map file extension to Prism language class. Anything unknown falls back to
# language-plaintext (no highlighting, still monospaced).
PRISM_LANG_BY_EXT = {
    # Shells
    ".sh": "language-bash",
    ".bash": "language-bash",
    ".zsh": "language-bash",
    ".ps1": "language-powershell",
    ".psm1": "language-powershell",
    ".psd1": "language-powershell",
    ".bat": "language-batch",
    ".cmd": "language-batch",
    # Scripting
    ".py": "language-python",
    ".rb": "language-ruby",
    ".pl": "language-perl",
    ".lua": "language-lua",
    # Web
    ".js": "language-javascript",
    ".mjs": "language-javascript",
    ".cjs": "language-javascript",
    ".ts": "language-typescript",
    ".tsx": "language-typescript",
    ".jsx": "language-javascript",
    ".php": "language-php",
    ".html": "language-html",
    ".htm": "language-html",
    ".xml": "language-xml",
    ".css": "language-css",
    # Compiled / systems
    ".go": "language-go",
    ".rs": "language-rust",
    ".c": "language-c",
    ".h": "language-c",
    ".cpp": "language-cpp",
    ".hpp": "language-cpp",
    ".cc": "language-cpp",
    ".cs": "language-csharp",
    ".java": "language-java",
    ".kt": "language-kotlin",
    ".kts": "language-kotlin",
    ".swift": "language-swift",
    # Assembly (NASM/Intel) — most exploit-dev and RE books use Intel syntax
    ".asm": "language-nasm",
    ".s": "language-nasm",
    ".nasm": "language-nasm",
    # Data + config
    ".sql": "language-sql",
    ".yaml": "language-yaml",
    ".yml": "language-yaml",
    ".json": "language-json",
    ".toml": "language-toml",
    ".ini": "language-ini",
    # Infra-as-code
    ".tf": "language-hcl",
    ".hcl": "language-hcl",
    ".dockerfile": "language-docker",
    # Other cyber-relevant
    ".http": "language-http",
    ".diff": "language-diff",
    ".patch": "language-diff",
}

# Filename-based mapping for files without conventional extensions.
PRISM_LANG_BY_NAME = {
    "Dockerfile": "language-docker",
    "dockerfile": "language-docker",
    "Makefile": "language-makefile",
    "makefile": "language-makefile",
}

# Map the Prism language class to the CDN component filename. Mostly identity
# but a few aliases (xml/html share "markup").
PRISM_CDN_NAME = {
    "language-bash": "bash",
    "language-python": "python",
    "language-powershell": "powershell",
    "language-batch": "batch",
    "language-yaml": "yaml",
    "language-json": "json",
    "language-toml": "toml",
    "language-ini": "ini",
    "language-sql": "sql",
    "language-c": "c",
    "language-cpp": "cpp",
    "language-rust": "rust",
    "language-go": "go",
    "language-javascript": "javascript",
    "language-typescript": "typescript",
    "language-csharp": "csharp",
    "language-java": "java",
    "language-kotlin": "kotlin",
    "language-swift": "swift",
    "language-ruby": "ruby",
    "language-php": "php",
    "language-perl": "perl",
    "language-lua": "lua",
    "language-nasm": "nasm",
    "language-docker": "docker",
    "language-http": "http",
    "language-hcl": "hcl",
    "language-diff": "diff",
    "language-makefile": "makefile",
    "language-css": "css",
    "language-xml": "markup",
    "language-html": "markup",
}

# Anything not in PRISM_CDN_NAME is treated as core/built-in and won't get an
# extra <script> tag (e.g. language-plaintext, which Prism core handles).
PRISM_CDN_COMPONENTS = set(PRISM_CDN_NAME.keys())


def _lang_from_ext(path: Path) -> str:
    # Filename match first (Dockerfile, Makefile, etc.) then extension.
    name_match = PRISM_LANG_BY_NAME.get(path.name)
    if name_match:
        return name_match
    return PRISM_LANG_BY_EXT.get(path.suffix.lower(), "language-plaintext")


# ----- Shortcode preprocessor -------------------------------------------------
#
# Processes shortcodes BEFORE markdown conversion. Strategy: replace each
# shortcode with a raw HTML block (markdown's "raw HTML" feature passes them
# through unmodified). Inline shortcodes become inline HTML; line-level and
# block shortcodes become block HTML separated by blank lines so markdown
# doesn't try to wrap them in <p>.

INLINE_CVE_RE = re.compile(r"!cve\s+(CVE-\d{4}-\d{4,7})", re.IGNORECASE)
INLINE_MITRE_RE = re.compile(r"!mitre\s+(T\d{4}(?:\.\d{3})?)", re.IGNORECASE)
LINE_CODEFILE_RE = re.compile(r"^!codefile\s+(\S+)\s*$", re.MULTILINE)
LINE_FIGURE_RE = re.compile(r'^!figure\s+(\S+)(?:\s+"([^"]*)")?\s*$', re.MULTILINE)

BLOCK_FENCE_RE = re.compile(
    r"^:::(\w+)(?:\s+(\S+))?\s*\n(.*?)^:::\s*$",
    re.MULTILINE | re.DOTALL,
)


def _render_codefile(chapter_dir: Path, rel_path: str) -> str:
    """Inline a code file as a <pre><code> block with a 'View full file' link."""
    file_path = (chapter_dir / rel_path).resolve()
    # Guard: must live under chapter_dir
    try:
        file_path.relative_to(chapter_dir.resolve())
    except ValueError:
        return f'<div class="note warning">Could not include {html.escape(rel_path)}: outside chapter directory.</div>'
    if not file_path.is_file():
        return f'<div class="note warning">Missing code file: {html.escape(rel_path)}</div>'
    lang_class = _lang_from_ext(file_path)
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_href = rel_path.replace("\\", "/")
    return (
        f'<pre><code class="{lang_class}">{html.escape(content)}</code></pre>\n'
        f'<a class="code-fullfile-link" href="{html.escape(rel_href, quote=True)}">View full file</a>'
    )


def _render_figure(rel_path: str, caption: str | None) -> str:
    src = html.escape(rel_path.replace("\\", "/"), quote=True)
    alt = html.escape(caption or rel_path)
    if caption:
        return (
            f'<figure class="chapter-figure">'
            f'<img src="{src}" alt="{alt}" />'
            f'<figcaption>{html.escape(caption)}</figcaption>'
            f"</figure>"
        )
    return f'<figure class="chapter-figure"><img src="{src}" alt="{alt}" /></figure>'


def _render_cve(cve_id: str) -> str:
    cve = cve_id.upper()
    return (
        f'<a class="cve-link" href="https://nvd.nist.gov/vuln/detail/{html.escape(cve, quote=True)}" '
        f'target="_blank" rel="noopener"><code>{html.escape(cve)}</code></a>'
    )


def _render_mitre(tech_id: str) -> str:
    tid = tech_id.upper()
    url_id = tid.replace(".", "/")
    return (
        f'<a class="mitre-link" href="https://attack.mitre.org/techniques/{html.escape(url_id, quote=True)}/" '
        f'target="_blank" rel="noopener"><code>{html.escape(tid)}</code></a>'
    )


def _render_note(flavour: str | None, inner_md: str) -> str:
    # inner_md is rendered separately below; here we just wrap it in a
    # placeholder div. Markdown will see this as raw HTML and pass through.
    # We embed the markdown-rendered inner content directly.
    import markdown

    inner_html = markdown.markdown(
        inner_md.strip(),
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    cls = "note"
    if flavour:
        flavour = flavour.lower().strip()
        if flavour in {"warning", "tip", "danger", "info"}:
            cls = f"note {flavour}"
    return f'<div class="{cls}">{inner_html}</div>'


def _render_terminal(shell_arg: str | None, inner: str) -> str:
    """Render a terminal session block.

    `shell_arg` is the optional language tag from ":::terminal <shell>". Defaults
    to bash. Supports any Prism language name (e.g. powershell, batch, python,
    sql for psql/mysql sessions). Bare ":::terminal" → bash.
    """
    lang = "language-bash"
    if shell_arg:
        candidate = f"language-{shell_arg.strip().lower()}"
        # Only use it if Prism actually has a component for it, otherwise the
        # class will sit on the <code> but no highlighter loads.
        if candidate in PRISM_CDN_COMPONENTS or candidate == "language-plaintext":
            lang = candidate
        else:
            # Unknown shell — fall back to plaintext to avoid pulling in an
            # unrelated highlighter.
            lang = "language-plaintext"
    return (
        f'<pre class="terminal"><code class="{lang}">'
        f"{html.escape(inner.rstrip())}"
        f"</code></pre>"
    )


def preprocess_shortcodes(md_text: str, chapter_dir: Path) -> str:
    """Expand all shortcodes to raw HTML inside the markdown text."""

    # Block fences (:::type ...\n:::) first, because their content may contain
    # inline shortcodes we want to leave alone (terminal output mentioning
    # "!cve" in a CVE description, for instance).
    def _block_sub(m: re.Match) -> str:
        block_type = m.group(1).lower()
        arg = m.group(2)
        inner = m.group(3)
        if block_type == "note":
            return "\n\n" + _render_note(arg, inner) + "\n\n"
        if block_type == "terminal":
            return "\n\n" + _render_terminal(arg, inner) + "\n\n"
        # Unknown block: emit as preformatted text so the source doesn't disappear
        return f"\n\n<pre>{html.escape(m.group(0))}</pre>\n\n"

    md_text = BLOCK_FENCE_RE.sub(_block_sub, md_text)

    # Line-level shortcodes (their own paragraph).
    md_text = LINE_CODEFILE_RE.sub(
        lambda m: "\n\n" + _render_codefile(chapter_dir, m.group(1)) + "\n\n",
        md_text,
    )
    md_text = LINE_FIGURE_RE.sub(
        lambda m: "\n\n" + _render_figure(m.group(1), m.group(2)) + "\n\n",
        md_text,
    )

    # Inline shortcodes (inside paragraphs).
    md_text = INLINE_CVE_RE.sub(lambda m: _render_cve(m.group(1)), md_text)
    md_text = INLINE_MITRE_RE.sub(lambda m: _render_mitre(m.group(1)), md_text)

    return md_text


# ----- Quiz rendering ---------------------------------------------------------

def _render_quiz_block(quiz_items: list[dict], section_id: str) -> str:
    if not quiz_items:
        return ""

    rendered_questions = []
    for i, item in enumerate(quiz_items, start=1):
        qid = f"{section_id}-q{i}"
        if "mcq" in item:
            q_text = item["mcq"]
            options = item.get("options") or []
            correct = item.get("correct")
            explain = item.get("explain", "")
            if not options:
                continue
            # Accept correct as 1-indexed int or letter ("a"-"d")
            if isinstance(correct, int):
                correct_idx = correct - 1
            elif isinstance(correct, str) and correct.lower() in "abcdefgh":
                correct_idx = ord(correct.lower()) - ord("a")
            else:
                correct_idx = 0
            correct_letter = chr(ord("a") + correct_idx)
            option_html = []
            for j, opt in enumerate(options):
                letter = chr(ord("a") + j)
                option_html.append(
                    f'<label class="quiz-option" data-value="{letter}">'
                    f'<input type="radio" name="{qid}">'
                    f"<span>{_render_inline_md(str(opt))}</span>"
                    f"</label>"
                )
            rendered_questions.append(
                f'<div class="quiz-question" data-type="mcq" data-correct="{correct_letter}">'
                f'<div class="q-text">{_render_inline_md(str(q_text))}</div>'
                f'<div class="quiz-options">{"".join(option_html)}</div>'
                f'<div class="quiz-actions"><button class="btn quiz-check-btn">Check answer</button></div>'
                f'<div class="quiz-explanation"><strong>Answer:</strong> {correct_letter}. {_render_inline_md(str(explain))}</div>'
                f"</div>"
            )
        elif "short" in item:
            q_text = item["short"]
            answer = item.get("answer", "")
            rendered_questions.append(
                f'<div class="quiz-question" data-type="short">'
                f'<div class="q-text">{_render_inline_md(str(q_text))}</div>'
                f'<input class="quiz-short-answer" type="text" placeholder="Type your answer">'
                f'<div class="quiz-actions"><button class="btn quiz-show-btn">Show model answer</button></div>'
                f'<div class="quiz-explanation"><strong>Model answer:</strong> {_render_inline_md(str(answer))}</div>'
                f"</div>"
            )

    if not rendered_questions:
        return ""

    n = len(rendered_questions)
    return (
        f'<details class="quiz-block">'
        f"<summary>Knowledge check ({n} question{'s' if n != 1 else ''})</summary>"
        f'{"".join(rendered_questions)}'
        f"</details>"
    )


def _render_inline_md(text: str) -> str:
    """Render a short bit of text as inline markdown.

    Used for quiz questions, options, and explanations. Allows inline code with
    backticks and the `!cve`/`!mitre` shortcodes, but produces no block-level
    elements (no <p> wrappers).
    """
    # Expand inline shortcodes first.
    text = INLINE_CVE_RE.sub(lambda m: _render_cve(m.group(1)), text)
    text = INLINE_MITRE_RE.sub(lambda m: _render_mitre(m.group(1)), text)
    # Backtick inline code: `foo` -> <code>foo</code>
    def _code(m):
        return f"<code>{html.escape(m.group(1))}</code>"

    # Protect inline-code segments from further escaping, then process the rest.
    parts = []
    last = 0
    for m in re.finditer(r"`([^`]+)`", text):
        parts.append(html.escape(text[last:m.start()]))
        parts.append(_code(m))
        last = m.end()
    parts.append(html.escape(text[last:]))
    out = "".join(parts)
    # Allow our own shortcode-emitted tags through. We escaped everything, so
    # any tag we generated above is already in-place because we appended raw
    # strings BEFORE escaping. To handle this cleanly, we apply shortcode
    # expansion AFTER escaping but on the un-escaped source first; the simplest
    # working approach: run shortcodes again on the final HTML string, since
    # the directive markers (`!cve`, `!mitre`) survive html.escape unchanged.
    out = INLINE_CVE_RE.sub(lambda m: _render_cve(m.group(1)), out)
    out = INLINE_MITRE_RE.sub(lambda m: _render_mitre(m.group(1)), out)
    return out


# ----- Sidebar from manifest --------------------------------------------------

def _sidebar(manifest: dict, current_dir: str, subsections: list[dict]) -> str:
    chapter_links = []
    for ch in manifest.get("chapters", []):
        is_active = ch.get("directory") == current_dir
        cls = "sidebar-link active" if is_active else "sidebar-link"
        status = ch.get("status", "pending")
        icon = "&#9679;" if status == "ready" else "&#9675;"
        chapter_links.append(
            f'<a class="{cls}" href="../{ch["directory"]}/index.html" '
            f'data-chapter-slug="{html.escape(ch["slug"], quote=True)}">'
            f'<span class="status-icon {status}">{icon}</span>'
            f'<span>{ch["number"]}. {html.escape(ch["title"])}</span>'
            f"</a>"
        )

    subsection_links = []
    for sub in subsections:
        subsection_links.append(
            f'<a class="sidebar-link" href="#{html.escape(sub["id"], quote=True)}">'
            f'<span class="status-icon incomplete">&#9675;</span>'
            f'<span>{html.escape(sub["title"])}</span>'
            f"</a>"
        )

    return (
        '<aside class="sidebar">'
        '<h2>Roadmap</h2>'
        '<a class="sidebar-link" href="../../index.html">'
        '<span class="status-icon">&larr;</span><span>Back to roadmap</span></a>'
        '<h2>Chapters</h2>'
        f'{"".join(chapter_links)}'
        '<h2>This chapter</h2>'
        f'{"".join(subsection_links)}'
        "</aside>"
    )


# ----- Resource cards ---------------------------------------------------------

def _resource_cards(chapter_dir: Path, card_count: int) -> str:
    cards = []
    if (chapter_dir / "anki-deck.apkg").exists() and card_count > 0:
        cards.append(
            f'<a class="resource-card" href="anki-deck.apkg" download>'
            f'<div class="resource-label">Flashcards</div>'
            f'<div class="resource-title">Anki Deck</div>'
            f'<div class="resource-desc">{card_count} cloze deletion cards</div></a>'
        )
    if (chapter_dir / "lab.html").exists():
        cards.append(
            '<a class="resource-card" href="lab.html">'
            '<div class="resource-label">Hands-on</div>'
            '<div class="resource-title">Lab Guide</div>'
            '<div class="resource-desc">Set up and walkthrough</div></a>'
        )
    elif (chapter_dir / "lab.ipynb").exists():
        cards.append(
            '<a class="resource-card" href="lab.ipynb" download>'
            '<div class="resource-label">Hands-on</div>'
            '<div class="resource-title">Jupyter Lab</div>'
            '<div class="resource-desc">Follow along in a notebook</div></a>'
        )
    code_dir = chapter_dir / "code-examples"
    if code_dir.is_dir():
        n_files = sum(1 for p in code_dir.iterdir() if p.is_file() and p.name != "index.html")
        if n_files > 0:
            cards.append(
                f'<a class="resource-card" href="code-examples/index.html">'
                f'<div class="resource-label">Source</div>'
                f'<div class="resource-title">Code Examples</div>'
                f'<div class="resource-desc">{n_files} standalone files</div></a>'
            )
    if not cards:
        return ""
    return f'<div class="resources">{"".join(cards)}</div>'


# ----- Chapter nav (prev/next) ------------------------------------------------

def _chapter_nav(manifest: dict, current_dir: str) -> str:
    chapters = manifest.get("chapters", [])
    idx = next((i for i, c in enumerate(chapters) if c.get("directory") == current_dir), -1)
    links = []
    if idx > 0:
        p = chapters[idx - 1]
        links.append(
            f'<a href="../{p["directory"]}/index.html" class="prev">'
            f'<div class="nav-label">&larr; Previous</div>'
            f'<div class="nav-title">{html.escape(p["title"])}</div></a>'
        )
    if 0 <= idx < len(chapters) - 1:
        n = chapters[idx + 1]
        links.append(
            f'<a href="../{n["directory"]}/index.html" class="next">'
            f'<div class="nav-label">Next &rarr;</div>'
            f'<div class="nav-title">{html.escape(n["title"])}</div></a>'
        )
    if not links:
        return ""
    return f'<nav class="chapter-nav">{"".join(links)}</nav>'


# ----- Prism script tags ------------------------------------------------------

def _prism_scripts_for(used_langs: set[str]) -> str:
    """Return the <link>+<script> tags Prism needs for the languages used.

    Skipped entirely if no language classes are present on the page (pure-prose
    chapters: threat-modelling, policy, methodology, etc.). Saves a CDN hit
    per chapter view.
    """
    # Filter to languages Prism has a component for. language-plaintext and
    # anything unknown is core-handled (no per-language component).
    components_needed = sorted(
        lang for lang in used_langs if lang in PRISM_CDN_COMPONENTS
    )
    if not used_langs:
        # No code anywhere on the page — skip the Prism CDN entirely.
        return ""
    base = (
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>'
    )
    components = [
        f'<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-{PRISM_CDN_NAME[lang]}.min.js"></script>'
        for lang in components_needed
    ]
    return base + "".join(components)


def _detect_used_langs(html_body: str) -> set[str]:
    # Allow hyphens for Prism languages like "objective-c" if they ever appear.
    return set(re.findall(r'class="(language-[a-z0-9+\-]+)"', html_body))


# ----- Page template ----------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="book-slug" content="{book_slug}">
  <meta name="chapter-slug" content="{chapter_slug}">
  <title>{title}</title>
  <link rel="stylesheet" href="../../assets/styles.css">
  {prism_scripts}
  <script>
    (function () {{
      var fromUrl = null;
      try {{ fromUrl = new URLSearchParams(window.location.search).get('theme'); }} catch (e) {{}}
      var theme = (fromUrl === 'light' || fromUrl === 'dark') ? fromUrl
        : localStorage.getItem('coursesmith-theme');
      if (theme === 'light' || theme === 'dark') {{
        document.documentElement.setAttribute('data-theme', theme);
        try {{ localStorage.setItem('coursesmith-theme', theme); }} catch (e) {{}}
      }}
    }})();
  </script>
</head>
<body>
<div class="layout">
{sidebar}
<main>
  <div class="topbar">
    <div class="breadcrumb">
      <a href="../../index.html">Roadmap</a> &nbsp;/&nbsp; Chapter {chapter_num}
    </div>
    <button class="btn" onclick="resetStudyProgress()">Reset progress</button>
    <button class="theme-toggle" type="button" aria-label="Switch theme"></button>
  </div>

  <h1>{chapter_title}</h1>
  {intro_html}

  {resource_cards}

  {subsections_html}

  {chapter_nav}
</main>
</div>
<script src="../../assets/script.js"></script>
</body>
</html>
"""

SUBSECTION_TEMPLATE = """<section class="subsection" data-subsection-id="{id}" id="{id}">
  <header class="subsection-header">
    <h2 class="subsection-title">{title}</h2>
    <span class="subsection-status">{n} of {total}</span>
  </header>
  {body}
  {quiz}
  <button class="btn primary complete-btn">Mark subsection complete</button>
</section>
"""


# ----- Main rendering ---------------------------------------------------------

def render_chapter(source_path: Path, manifest_path: Path, output_path: Path) -> None:
    _ensure_deps()
    import yaml
    import markdown

    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chapter_dir = source_path.parent
    current_dir = chapter_dir.name

    # Find this chapter in the manifest (for nav + sidebar context)
    chapter_meta = next(
        (c for c in manifest.get("chapters", []) if c.get("directory") == current_dir),
        None,
    )
    if chapter_meta is None:
        raise SystemExit(
            f"Chapter directory '{current_dir}' not found in manifest at {manifest_path}"
        )

    book = manifest.get("book", {})
    book_title = book.get("title", "Study Guide")
    book_slug = book.get("slug", "book")
    chapter_num = chapter_meta["number"]
    chapter_title = chapter_meta["title"]
    chapter_slug = chapter_meta["slug"]
    card_count = chapter_meta.get("card_count", 0)

    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )

    # Intro
    intro_md = (source.get("intro") or "").strip()
    if intro_md:
        intro_md_expanded = preprocess_shortcodes(intro_md, chapter_dir)
        intro_html = md.convert(intro_md_expanded)
        md.reset()
    else:
        intro_html = ""

    # Subsections
    subsections = source.get("subsections") or []
    if not subsections:
        raise SystemExit("Chapter source has no subsections.")
    total = len(subsections)
    subsection_blocks = []
    for i, sub in enumerate(subsections, start=1):
        sid = sub["id"]
        stitle = sub["title"]
        body_md = (sub.get("body") or "").strip()
        body_md_expanded = preprocess_shortcodes(body_md, chapter_dir)
        body_html = md.convert(body_md_expanded)
        md.reset()
        quiz_html = _render_quiz_block(sub.get("quiz") or [], sid)
        subsection_blocks.append(
            SUBSECTION_TEMPLATE.format(
                id=html.escape(sid, quote=True),
                title=html.escape(stitle),
                n=i,
                total=total,
                body=body_html,
                quiz=quiz_html,
            )
        )
    subsections_html = "\n".join(subsection_blocks)

    # Detect Prism languages used anywhere in the body for selective CDN includes
    used_langs = _detect_used_langs(intro_html) | _detect_used_langs(subsections_html)
    prism_scripts = _prism_scripts_for(used_langs)

    # Sidebar (manifest-driven)
    sidebar_subsections = [{"id": s["id"], "title": s["title"]} for s in subsections]
    sidebar = _sidebar(manifest, current_dir, sidebar_subsections)

    # Resource cards
    resource_cards = _resource_cards(chapter_dir, card_count)

    # Chapter prev/next nav
    chapter_nav = _chapter_nav(manifest, current_dir)

    page = PAGE.format(
        book_slug=html.escape(book_slug, quote=True),
        chapter_slug=html.escape(chapter_slug, quote=True),
        title=html.escape(f"{chapter_title} - {book_title}"),
        chapter_num=chapter_num,
        chapter_title=html.escape(chapter_title),
        intro_html=intro_html,
        resource_cards=resource_cards,
        subsections_html=subsections_html,
        sidebar=sidebar,
        chapter_nav=chapter_nav,
        prism_scripts=prism_scripts,
    )

    output_path.write_text(page, encoding="utf-8")
    print(f"Wrote {output_path} ({total} subsections, {len(used_langs)} prism langs)")


def main():
    p = argparse.ArgumentParser(description="Render a chapter.yaml source to index.html.")
    p.add_argument("--source", required=True, type=Path, help="Path to chapter.yaml")
    p.add_argument("--manifest", required=True, type=Path, help="Path to manifest.json")
    p.add_argument("--output", required=True, type=Path, help="Path to write index.html")
    args = p.parse_args()
    render_chapter(args.source, args.manifest, args.output)


if __name__ == "__main__":
    main()
