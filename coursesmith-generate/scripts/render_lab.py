#!/usr/bin/env python3
"""Render a chapter's lab-guide.md into a styled lab.html that matches the
course theme. Keeps the markdown source intact alongside the HTML.

Usage:
    python render_lab.py \
        --input  /path/to/chapters/NN-slug/lab-guide.md \
        --output /path/to/chapters/NN-slug/lab.html \
        --book-title "Black Hat Bash" \
        --chapter-num 1 \
        --chapter-title "Bash Basics"

Auto-installs `markdown` if missing.
"""
from __future__ import annotations

import argparse
import html
import subprocess
import sys
from pathlib import Path


def _ensure_markdown():
    try:
        import markdown  # noqa: F401
    except ImportError:
        print("markdown not found, installing...", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "markdown"]
        )


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_esc} - Lab</title>
  <link rel="stylesheet" href="../../assets/styles.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-bash.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-powershell.min.js"></script>
  <style>
    /* Lab-page-specific layout: single column, no sidebar */
    .lab-page {{
      max-width: var(--max-width);
      margin: 0 auto;
      padding: 1.5rem 1.25rem 4rem;
    }}
    .lab-page table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0 1.5rem;
    }}
    .lab-page th, .lab-page td {{
      border-bottom: 1px solid var(--border-subtle);
      padding: 0.55rem 0.75rem;
      text-align: left;
      vertical-align: top;
    }}
    .lab-page th {{
      color: var(--text-secondary);
      font-weight: 600;
      background: var(--bg-elevated);
    }}
    .lab-page blockquote {{
      border-left: 3px solid var(--accent);
      background: var(--bg-elevated);
      padding: 0.75rem 1rem;
      margin: 1rem 0;
      border-radius: var(--radius-small);
      color: var(--text-secondary);
    }}
    .lab-page hr {{
      border: none;
      border-top: 1px solid var(--border-subtle);
      margin: 2rem 0;
    }}
    .lab-source-link {{
      display: inline-block;
      margin-top: 0.5rem;
      font-size: 0.9rem;
      color: var(--text-muted);
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

<div class="lab-page">
  <div class="topbar">
    <div class="breadcrumb">
      <a href="../../index.html">Roadmap</a> &nbsp;/&nbsp;
      <a href="index.html">Chapter {chapter_num}</a> &nbsp;/&nbsp; Lab
    </div>
    <button class="theme-toggle" type="button" aria-label="Switch theme"></button>
  </div>

  {body}

  <a class="lab-source-link" href="lab-guide.md" download>Download markdown source</a>
</div>

<script src="../../assets/script.js"></script>
</body>
</html>
"""


def render(md_path: Path, out_path: Path, book_title: str, chapter_num: int, chapter_title: str) -> None:
    _ensure_markdown()
    import markdown

    md_text = md_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
        output_format="html5",
    )

    page = PAGE_TEMPLATE.format(
        title_esc=html.escape(f"{book_title} - Chapter {chapter_num}: {chapter_title}"),
        chapter_num=chapter_num,
        body=body_html,
    )
    out_path.write_text(page, encoding="utf-8")
    print(f"Wrote {out_path}")


def main():
    p = argparse.ArgumentParser(description="Render lab-guide.md to a styled lab.html.")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--book-title", required=True)
    p.add_argument("--chapter-num", required=True, type=int)
    p.add_argument("--chapter-title", required=True)
    args = p.parse_args()

    render(args.input, args.output, args.book_title, args.chapter_num, args.chapter_title)


if __name__ == "__main__":
    main()
