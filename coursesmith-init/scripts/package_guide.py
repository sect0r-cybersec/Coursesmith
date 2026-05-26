#!/usr/bin/env python3
"""
package_guide.py

Zip a study guide directory into a single .zip the user can download and
extract anywhere. Preserves the directory structure exactly so the
relative links inside the HTML files keep working.

Usage:
    python package_guide.py --source study-guide-black-hat-python --output /mnt/user-data/outputs/study-guide-black-hat-python.zip

The zip contains the study-guide directory itself at its root, so when the
user extracts it they get a folder with the right name (not a pile of loose
files).
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path


def package(source: Path, output: Path) -> int:
    if not source.exists():
        print(f"Error: source directory does not exist: {source}", file=sys.stderr)
        return 1
    if not source.is_dir():
        print(f"Error: source is not a directory: {source}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    parent = source.parent

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source):
            # Skip noise: .DS_Store, __pycache__, .ipynb_checkpoints, .git
            dirs[:] = [d for d in dirs if d not in {"__pycache__", ".ipynb_checkpoints", ".git"}]
            for f in files:
                if f in {".DS_Store"}:
                    continue
                full = Path(root) / f
                arc = full.relative_to(parent)
                zf.write(full, arc)
                file_count += 1
                total_bytes += full.stat().st_size

    size_kb = output.stat().st_size / 1024
    print(f"Packaged {file_count} files ({total_bytes / 1024:.1f} KB uncompressed) into {output} ({size_kb:.1f} KB)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Package a study guide directory into a zip.")
    parser.add_argument("--source", required=True, help="Path to the study-guide-{slug}/ directory.")
    parser.add_argument("--output", required=True, help="Output .zip path.")
    args = parser.parse_args()

    sys.exit(package(Path(args.source), Path(args.output)))


if __name__ == "__main__":
    main()
