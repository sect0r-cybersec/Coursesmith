#!/usr/bin/env python3
"""Render a code-examples/index.html that lists every file in a chapter's
code-examples directory with the same theme as the rest of the course, so the
user no longer relies on the browser's raw directory index.

Usage:
    python render_code_index.py \
        --dir /path/to/chapters/NN-slug/code-examples \
        --book-title "Black Hat Bash" \
        --chapter-num 1 \
        --chapter-title "Bash Basics"

Writes <dir>/index.html.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path

LANG_BY_EXT = {
    ".sh": "Bash",
    ".bash": "Bash",
    ".py": "Python",
    ".ps1": "PowerShell",
    ".rb": "Ruby",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".java": "Java",
    ".php": "PHP",
    ".sql": "SQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".md": "Markdown",
    ".txt": "Text",
}

PAGE = """<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Code Examples - {title_esc}</title>
  <link rel="stylesheet" href="../../../assets/styles.css">
  <style>
    .code-index {{
      max-width: var(--max-width);
      margin: 0 auto;
      padding: 1.5rem 1.25rem 4rem;
    }}
    .file-list {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.6rem;
      margin-top: 1.5rem;
    }}
    .file-card {{
      display: grid;
      grid-template-columns: 2.25rem 1fr auto;
      align-items: center;
      gap: 0.9rem;
      padding: 0.75rem 1rem;
      background: var(--bg-glass);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-small);
      transition: background 0.15s, border-color 0.15s, transform 0.05s;
      text-decoration: none;
      color: var(--text-primary);
    }}
    .file-card:hover {{
      background: var(--bg-glass-hover);
      border-color: var(--border-default);
    }}
    .file-card:active {{
      transform: translateY(1px);
    }}
    .file-icon {{
      font-family: var(--font-mono);
      font-size: 0.85rem;
      color: var(--accent);
      background: var(--accent-dim);
      border-radius: var(--radius-small);
      width: 2.25rem;
      height: 2.25rem;
      display: grid;
      place-items: center;
    }}
    .file-name {{
      font-family: var(--font-mono);
      font-size: 0.95rem;
      color: var(--text-primary);
    }}
    .file-meta {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 0.15rem;
    }}
    .file-tag {{
      font-size: 0.75rem;
      padding: 0.15rem 0.5rem;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: 99px;
      color: var(--text-secondary);
      white-space: nowrap;
    }}
    .file-card a {{ border: 0; }}
    .empty {{
      color: var(--text-muted);
      font-style: italic;
      padding: 2rem 0;
    }}
  </style>
  <script>
    (function () {{
      var saved = localStorage.getItem('coursesmith-theme');
      if (saved === 'light' || saved === 'dark') {{
        document.documentElement.setAttribute('data-theme', saved);
      }}
    }})();
  </script>
</head>
<body>

<div class="code-index">

  <div class="topbar">
    <div class="breadcrumb">
      <a href="../../../index.html">Roadmap</a> &nbsp;/&nbsp;
      <a href="../index.html">Chapter {chapter_num}</a> &nbsp;/&nbsp; Code examples
    </div>
    <button class="theme-toggle" type="button" aria-label="Switch theme"></button>
  </div>

  <h1>Code examples</h1>
  <p>Standalone scripts from <em>{book_title_esc}</em>, Chapter {chapter_num}: {chapter_title_esc}. Click a file to view it in your browser, or right-click to download.</p>

  <div class="file-list">
  {rows}
  </div>

</div>

<script src="../../../assets/script.js"></script>
</body>
</html>
"""

ROW = """    <a class="file-card" href="{href}">
      <span class="file-icon">{ext_short}</span>
      <div>
        <div class="file-name">{name_esc}</div>
        <div class="file-meta">{line_count} lines &middot; {byte_count} bytes</div>
      </div>
      <span class="file-tag">{lang_esc}</span>
    </a>"""


def line_count(p: Path) -> int:
    try:
        with p.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def render(directory: Path, book_title: str, chapter_num: int, chapter_title: str) -> Path:
    files = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.name != "index.html"),
        key=lambda p: p.name,
    )

    if not files:
        rows = '<div class="empty">No code examples were extracted for this chapter.</div>'
    else:
        rendered = []
        for p in files:
            ext = p.suffix.lower()
            lang = LANG_BY_EXT.get(ext, ext.lstrip(".").upper() or "FILE")
            rendered.append(
                ROW.format(
                    href=html.escape(p.name, quote=True),
                    ext_short=html.escape(ext.lstrip(".") or "·"),
                    name_esc=html.escape(p.name),
                    line_count=line_count(p),
                    byte_count=p.stat().st_size,
                    lang_esc=html.escape(lang),
                )
            )
        rows = "\n".join(rendered)

    page = PAGE.format(
        title_esc=html.escape(f"{book_title} - Chapter {chapter_num}: {chapter_title}"),
        chapter_num=chapter_num,
        book_title_esc=html.escape(book_title),
        chapter_title_esc=html.escape(chapter_title),
        rows=rows,
    )

    out_path = directory / "index.html"
    out_path.write_text(page, encoding="utf-8")
    print(f"Wrote {out_path} ({len(files)} files)")
    return out_path


def main():
    p = argparse.ArgumentParser(description="Render code-examples/index.html.")
    p.add_argument("--dir", required=True, type=Path)
    p.add_argument("--book-title", required=True)
    p.add_argument("--chapter-num", required=True, type=int)
    p.add_argument("--chapter-title", required=True)
    args = p.parse_args()

    render(args.dir, args.book_title, args.chapter_num, args.chapter_title)


if __name__ == "__main__":
    main()
