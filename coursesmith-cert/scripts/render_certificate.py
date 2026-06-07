"""Render a Coursesmith certificate of completion.

Usage:
    python render_certificate.py \\
        --manifest path/to/manifest.json \\
        --name "Jane Doe" \\
        [--theme dark|light] \\
        [--accent "#ff4136"] \\
        [--date "26 May 2026"]

What it does:
    1. Loads manifest.json; refuses if any chapter is not status="ready".
    2. Resolves the accent palette (override or cover-derived, with default
       green fallback).
    3. Resolves the author (PDF metadata then title-page scrape, or omitted).
    4. Generates a deterministic cert ID from book_slug + completion_date.
    5. Substitutes tokens into templates/certificate.html.
    6. Renders the resolved HTML through headless Chromium (Playwright) at
       viewport 1200x800.
    7. Writes {output_dir}/certificate.png.
    8. Updates manifest.json with a certificate block and bumps
       last_modified.
    9. Injects (or replaces) the certificate card on the roadmap
       index.html.

Auto-installs playwright, Pillow, pypdf on first run; runs
`playwright install chromium` if the browser cache is empty.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ----------------------------------------------------------------------------
# Dependency bootstrap
# ----------------------------------------------------------------------------


def _pip_install(*packages: str) -> None:
    print(f"  installing: {' '.join(packages)}", file=sys.stderr)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", *packages],
    )


def _ensure_dependencies() -> None:
    """Lazily install playwright, Pillow, pypdf on first run."""
    missing = []
    try:
        import playwright  # noqa: F401
    except ImportError:
        missing.append("playwright")
    try:
        import PIL  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    try:
        import pypdf  # noqa: F401
    except ImportError:
        missing.append("pypdf")
    if missing:
        _pip_install(*missing)


def _ensure_chromium() -> None:
    """Run `playwright install chromium` if the cache is empty.
    Cheap no-op if Chromium is already installed."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        print("  chromium install failed; try running:", file=sys.stderr)
        print(f"    {sys.executable} -m playwright install chromium",
              file=sys.stderr)
        raise


# ----------------------------------------------------------------------------
# Manifest handling
# ----------------------------------------------------------------------------


def _load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        sys.exit(f"manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _validate_chapters_ready(manifest: dict) -> None:
    """Refuse cert generation if any chapter is not status='ready'."""
    pending = [
        ch for ch in manifest.get("chapters", [])
        if ch.get("status") != "ready"
    ]
    if pending:
        lines = ", ".join(
            f"{ch.get('number')} ({ch.get('status')})" for ch in pending
        )
        sys.exit(
            f"Some chapters are still not ready: {lines}.\n"
            "Finish them with `coursesmith-generate` first."
        )


def _write_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ----------------------------------------------------------------------------
# Date and ID
# ----------------------------------------------------------------------------


_MONTHS_BRITISH = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _british_date(d: datetime.date) -> str:
    return f"{d.day} {_MONTHS_BRITISH[d.month - 1]} {d.year}"


def _generate_cert_id(book_slug: str, iso_date: str) -> str:
    """CSM-XXXX-YYYY where XXXX is sha256(slug|date)[:4] uppercase."""
    digest = hashlib.sha256(
        f"{book_slug}|{iso_date}".encode("utf-8")
    ).hexdigest()
    year = iso_date[:4]
    return f"CSM-{digest[:4].upper()}-{year}"


# ----------------------------------------------------------------------------
# Template substitution
# ----------------------------------------------------------------------------


_BOOK_AUTHOR_DIV_RE = re.compile(
    r'\s*<div class="book-author">.*?</div>',
    re.DOTALL,
)


def _resolve_template(
    template_path: Path,
    substitutions: dict[str, str],
    author: str | None,
    theme: str,
) -> str:
    html = template_path.read_text(encoding="utf-8")
    # Strip the author div if no author was found, before substitution
    # (so leftover {{BOOK_AUTHOR}} can't bleed through).
    if author is None:
        html = _BOOK_AUTHOR_DIV_RE.sub("", html)
    # Apply all token substitutions.
    for token, value in substitutions.items():
        html = html.replace(token, value)
    # Set data-theme on the <html> tag.
    html = html.replace("<html lang=\"en\">",
                        f'<html lang="en" data-theme="{theme}">', 1)
    return html


# ----------------------------------------------------------------------------
# Playwright render
# ----------------------------------------------------------------------------


def _render_to_png(html_path: Path, png_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 800},
                device_scale_factor=2,  # crisper screenshot
            )
            page = context.new_page()
            page.goto(html_path.as_uri())
            # Wait for fonts (JetBrains Mono loaded from CDN).
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(200)  # paint settle
            page.screenshot(
                path=str(png_path),
                full_page=False,
                omit_background=False,
            )
        finally:
            browser.close()


# ----------------------------------------------------------------------------
# Roadmap card injection
# ----------------------------------------------------------------------------


_CERT_CARD_START = "<!-- coursesmith-cert:card-start -->"
_CERT_CARD_END = "<!-- coursesmith-cert:card-end -->"


def _render_cert_card_html(
    cert: dict, book_title: str, date_human: str
) -> str:
    """Build the certificate card HTML to inject into the roadmap."""
    return (
        f"{_CERT_CARD_START}\n"
        f'<div class="roadmap-node certificate-node">\n'
        f'  <a class="roadmap-card certificate-card ready" '
        f'href="certificate.png" target="_blank">\n'
        f'    <div class="chapter-num">CERTIFICATE</div>\n'
        f'    <div class="chapter-title">'
        f'{_html_escape(cert["name"])} &middot; {_html_escape(book_title)}'
        f'</div>\n'
        f'    <div class="chapter-meta">\n'
        f'      <span class="status-badge ready">'
        f'<span class="status-icon complete">&#10003;</span> '
        f'Completed</span>\n'
        f'      <span>{_html_escape(cert["id"])}</span>\n'
        f'      <span>Issued {_html_escape(date_human)}</span>\n'
        f'    </div>\n'
        f'  </a>\n'
        f'</div>\n'
        f"{_CERT_CARD_END}"
    )


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;")
              .replace('"', "&quot;"))


def _inject_cert_card_into_roadmap(
    roadmap_path: Path, cert_card_html: str
) -> None:
    """Insert or replace the cert card in index.html.

    On first run, inserts the card immediately after `<div class="roadmap">`.
    On subsequent runs, finds the marker block and replaces it.
    """
    if not roadmap_path.exists():
        print(f"  warning: {roadmap_path} not found; skipping roadmap update",
              file=sys.stderr)
        return
    html = roadmap_path.read_text(encoding="utf-8")

    if _CERT_CARD_START in html and _CERT_CARD_END in html:
        # Replace existing block.
        pattern = re.compile(
            re.escape(_CERT_CARD_START) + r".*?" + re.escape(_CERT_CARD_END),
            re.DOTALL,
        )
        html = pattern.sub(cert_card_html, html, count=1)
    else:
        # Insert after the roadmap container's opening tag.
        marker_re = re.compile(r'(<div\s+class="roadmap"[^>]*>)')
        m = marker_re.search(html)
        if not m:
            print(
                "  warning: could not find <div class=\"roadmap\"> in "
                f"{roadmap_path}; skipping roadmap update",
                file=sys.stderr,
            )
            return
        insertion = m.group(1) + "\n" + cert_card_html
        html = html[: m.start()] + insertion + html[m.end():]

    roadmap_path.write_text(html, encoding="utf-8")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Coursesmith certificate of completion.",
    )
    parser.add_argument("--manifest", required=True, type=Path,
                        help="Path to the study-guide manifest.json")
    parser.add_argument("--name", required=True,
                        help="Name to print on the certificate")
    parser.add_argument("--theme", choices=("dark", "light"), default="dark",
                        help="Certificate theme (default: dark)")
    parser.add_argument("--accent",
                        help="Override accent hex, e.g. '#ff4136'")
    parser.add_argument("--date",
                        help="Override completion date in British format, "
                             "e.g. '26 May 2026' (defaults to today)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    print("coursesmith-cert: preparing", file=sys.stderr)
    _ensure_dependencies()

    # Imports that depend on freshly-installed packages.
    from extract_accent import (
        extract_from_pdf as extract_accent_from_pdf,
        palette_from_hex,
    )
    from extract_author import extract_from_pdf as extract_author_from_pdf

    manifest_path: Path = args.manifest.resolve()
    manifest = _load_manifest(manifest_path)
    _validate_chapters_ready(manifest)

    output_dir = manifest_path.parent
    source_pdf = manifest.get("source_pdf")
    if not source_pdf:
        sys.exit("manifest is missing 'source_pdf' (required to extract "
                 "the cover and author)")
    book_title = manifest.get("title") or manifest.get("book_title") \
        or "this book"
    book_slug = manifest.get("slug") or output_dir.name

    # Date.
    if args.date:
        date_human = args.date
        # Parse for the cert ID.
        try:
            d = datetime.datetime.strptime(args.date, "%d %B %Y").date()
        except ValueError:
            sys.exit(f"--date must be in British format 'DD Month YYYY', "
                     f"got {args.date!r}")
    else:
        d = datetime.date.today()
        date_human = _british_date(d)
    iso_date = d.isoformat()

    cert_id = _generate_cert_id(book_slug, iso_date)

    # Accent palette.
    if args.accent:
        palette = palette_from_hex(args.accent)
    else:
        print("coursesmith-cert: deriving accent from cover", file=sys.stderr)
        palette = extract_accent_from_pdf(source_pdf)
        if palette.source == "default":
            print("  no vivid colour found on cover; using Coursesmith "
                  "default green", file=sys.stderr)

    # Author.
    print("coursesmith-cert: extracting author", file=sys.stderr)
    author = extract_author_from_pdf(source_pdf)
    book_author_display = f"by {author}" if author else None
    if author:
        print(f"  using author: {author}", file=sys.stderr)
    else:
        print("  no trustworthy author found; omitting", file=sys.stderr)

    # Substitutions.
    substitutions = {
        "{{NAME}}": _html_escape(args.name),
        "{{BOOK_TITLE}}": _html_escape(book_title),
        "{{COMPLETION_DATE}}": _html_escape(date_human),
        "{{CERT_ID}}": _html_escape(cert_id),
        **palette.to_substitutions(),
    }
    if book_author_display is not None:
        substitutions["{{BOOK_AUTHOR}}"] = _html_escape(book_author_display)

    # Resolve template.
    template_path = Path(__file__).parent.parent / "templates" \
        / "certificate.html"
    if not template_path.exists():
        sys.exit(f"template not found: {template_path}")
    resolved_html = _resolve_template(
        template_path, substitutions, author, args.theme,
    )

    # Render.
    print("coursesmith-cert: rendering PNG", file=sys.stderr)
    _ensure_chromium()
    png_path = output_dir / "certificate.png"
    with tempfile.TemporaryDirectory() as work_dir:
        html_temp = Path(work_dir) / "certificate.html"
        html_temp.write_text(resolved_html, encoding="utf-8")
        try:
            _render_to_png(html_temp, png_path)
        except Exception as exc:
            sys.exit(f"rendering failed: {exc}")

    # Update manifest.
    cert_block = {
        "name": args.name,
        "id": cert_id,
        "accent": palette.dark_hex,
        "accent_source": palette.source,
        "theme": args.theme,
        "author_used": author,
        "path": "certificate.png",
        "generated_at": datetime.datetime.utcnow().isoformat(
            timespec="seconds"
        ) + "Z",
    }
    manifest["certificate"] = cert_block
    manifest["last_modified"] = cert_block["generated_at"]
    _write_manifest(manifest_path, manifest)

    # Roadmap card injection.
    roadmap_path = output_dir / "index.html"
    cert_card_html = _render_cert_card_html(
        cert_block, book_title, date_human,
    )
    _inject_cert_card_into_roadmap(roadmap_path, cert_card_html)

    # Done.
    print(f"\ncertificate written: {png_path}")
    print(f"cert id: {cert_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
