"""Extract a book author (or publisher fallback) from a PDF.

Public surface:
    extract_from_pdf(pdf_path) -> str | None

Returns a clean name string with no 'by ' prefix, ready for the cert
template to wrap as 'by {name}'. Returns None if nothing trustworthy was
found, in which case the renderer strips the author element entirely.

Strategy:
  1. PDF metadata: /Author first, /Publisher as fallback, with a blacklist
     for typesetter tools and emails.
  2. Title-page text scrape via pdftotext, three patterns in confidence
     order: explicit 'by X' lines, title/author line pairs, known publisher
     imprints.
  3. Sanitise (strip 'by ', collapse whitespace, title-case if all-caps,
     truncate at 60 chars).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Optional


# Words that indicate the metadata field is a tool, not a person/publisher.
# Lowercased, matched as substrings.
_BLACKLIST = (
    "adobe", "indesign", "quark", "latex", "ms word", "microsoft word",
    "microsoft", "unknown", "admin", "user", "untitled", "default",
    "framemaker", "pagemaker", "publisher tool", "antenna house",
    "pdfsharp", "itext", "pdfkit", "ghostscript", "calibre",
    "pdfplumber", "wkhtmltopdf",
)

_KNOWN_PUBLISHERS = (
    "No Starch Press",
    "O'Reilly Media",
    "O'Reilly",
    "Manning Publications",
    "Manning",
    "Packt Publishing",
    "Packt",
    "Pragmatic Bookshelf",
    "The Pragmatic Programmers",
    "Wiley",
    "Apress",
    "Addison-Wesley",
    "Pearson",
    "MIT Press",
    "Cambridge University Press",
    "Oxford University Press",
    "Springer",
)

_MAX_LEN = 60
_BY_LINE_RE = re.compile(r"^\s*by\s+([A-Z][A-Za-z .\-']{2,60})\s*$")
_NAME_LINE_RE = re.compile(r"^[A-Z][A-Za-z .\-']{2,60}(,\s*Ph\.?D\.?)?$")
_TITLE_LIKE_RE = re.compile(r"^[A-Z][A-Za-z0-9 :,&\-']{4,80}$")


def _is_blacklisted(value: str) -> bool:
    lo = value.lower()
    if "@" in lo:
        return True
    if len(value) > 80:
        return True
    return any(bad in lo for bad in _BLACKLIST)


def _try_metadata(pdf_path: str) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(pdf_path)
        meta = reader.metadata or {}
    except Exception:
        return None

    for key in ("/Author", "/Publisher"):
        raw = meta.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if not value:
            continue
        if _is_blacklisted(value):
            continue
        return value
    return None


def _try_scrape_titlepage(pdf_path: str) -> Optional[str]:
    if not shutil.which("pdftotext"):
        return None
    try:
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "3", "-layout", pdf_path, "-"],
            check=True, capture_output=True, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    text = result.stdout

    lines = [line.strip() for line in text.splitlines()]
    non_empty = [line for line in lines if line]

    # Pattern 1: explicit "by X" line.
    for line in non_empty:
        m = _BY_LINE_RE.match(line)
        if m:
            candidate = m.group(1).strip()
            if not _is_blacklisted(candidate):
                return candidate

    # Pattern 2: title/author line pair. Scan adjacent non-empty pairs.
    for i in range(len(non_empty) - 1):
        title_candidate = non_empty[i]
        name_candidate = non_empty[i + 1]
        if (_TITLE_LIKE_RE.match(title_candidate)
                and _NAME_LINE_RE.match(name_candidate)
                and not _is_blacklisted(name_candidate)):
            # Reject if the "name" line ends with a period (it's a sentence).
            if not name_candidate.rstrip().endswith("."):
                return name_candidate

    # Pattern 3: known publisher imprint anywhere in the scrape.
    lowered = text.lower()
    for pub in _KNOWN_PUBLISHERS:
        if pub.lower() in lowered:
            return pub

    return None


def _sanitise(name: str) -> str:
    # Strip leading "by " (case-insensitive).
    if name.lower().startswith("by "):
        name = name[3:].strip()
    # Collapse whitespace.
    name = " ".join(name.split())
    # Strip trailing periods (preserve "Ph.D." style by checking length > 1).
    while name.endswith(".") and not name.endswith("D."):
        name = name[:-1].rstrip()
    # Title-case if entirely uppercase.
    if name.isupper() and len(name) > 3:
        name = name.title()
    # Truncate.
    if len(name) > _MAX_LEN:
        name = name[: _MAX_LEN - 7].rstrip() + " et al."
    return name


def extract_from_pdf(pdf_path: str) -> Optional[str]:
    """Returns a clean author/publisher string, or None if nothing found."""
    raw = _try_metadata(pdf_path)
    if raw is None:
        raw = _try_scrape_titlepage(pdf_path)
    if raw is None:
        return None
    clean = _sanitise(raw)
    if not clean:
        return None
    return clean


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: extract_author.py <pdf-path>", file=sys.stderr)
        sys.exit(2)
    result = extract_from_pdf(sys.argv[1])
    if result is None:
        print("(no author found)")
        sys.exit(1)
    print(result)
