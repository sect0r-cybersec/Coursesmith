#!/usr/bin/env python3
"""
generate_anki.py

Generate a cloze-deletion Anki deck (.apkg) from a JSON list of cards.

Usage:
    python generate_anki.py --cards cards.json --deck-name "My Book :: Chapter 1" --output anki-deck.apkg

Input JSON format:
    [
        {
            "text": "The {{c1::TCP}} protocol is connection-oriented.",
            "extra": "Optional extra context shown on the back of the card."
        },
        ...
    ]

Cloze syntax:
    {{c1::hidden text}}                    -> simple cloze
    {{c1::hidden text::hint}}              -> cloze with a hint
    Multiple cloze numbers ({{c1::}}, {{c2::}}, etc.) create separate cards from one note.

Notes:
    - genanki is auto-installed if missing.
    - Deck IDs and model IDs must be stable per deck name (so re-running updates rather than duplicates).
      We hash the deck name to derive these.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def ensure_genanki():
    """Install genanki if it's not available."""
    try:
        import genanki  # noqa: F401
        return
    except ImportError:
        pass

    print("genanki not found, installing...", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "genanki", "--break-system-packages", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Retry without --break-system-packages for environments that don't support it
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "genanki", "--quiet"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("Failed to install genanki:", result.stderr, file=sys.stderr)
            sys.exit(1)


def stable_id(seed: str, span: int = 1_000_000_000) -> int:
    """Derive a stable integer ID from a string seed.

    Anki uses these to identify decks/models. If we used random IDs,
    re-running the generator would create duplicate decks rather than updating.
    """
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(h[:12], 16) % span + 1_000_000_000


def build_deck(deck_name: str, cards: list) -> "genanki.Deck":
    import genanki

    deck_id = stable_id(f"deck::{deck_name}")
    model_id = stable_id("model::cloze::study-guide-v1")

    cloze_model = genanki.Model(
        model_id,
        "Study Guide Cloze",
        fields=[
            {"name": "Text"},
            {"name": "Extra"},
        ],
        templates=[
            {
                "name": "Cloze Card",
                "qfmt": "{{cloze:Text}}",
                "afmt": "{{cloze:Text}}<br><br><div class='extra'>{{Extra}}</div>",
            },
        ],
        css="""
        .card {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 18px;
            text-align: left;
            color: #e8ecf4;
            background-color: #0a0e1a;
            padding: 24px;
            line-height: 1.6;
        }
        .cloze {
            color: #7cf07c;
            font-weight: 600;
        }
        .extra {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(255,255,255,0.12);
            color: #a8b2c7;
            font-size: 0.9em;
        }
        code, pre {
            font-family: "JetBrains Mono", "Fira Code", monospace;
            background: rgba(20, 26, 42, 0.8);
            color: #c8d4ec;
            padding: 0.15em 0.4em;
            border-radius: 4px;
            font-size: 0.95em;
        }
        pre {
            display: block;
            padding: 1rem;
            margin: 0.5rem 0;
            overflow-x: auto;
        }
        """,
        model_type=genanki.Model.CLOZE,
    )

    deck = genanki.Deck(deck_id, deck_name)

    for card in cards:
        text = card.get("text", "").strip()
        extra = card.get("extra", "").strip()
        if not text:
            continue
        if "{{c" not in text:
            print(f"Warning: card has no cloze deletion, skipping: {text[:60]}", file=sys.stderr)
            continue
        note = genanki.Note(
            model=cloze_model,
            fields=[text, extra],
            guid=genanki.guid_for(deck_name, text),
        )
        deck.add_note(note)

    return deck


def main():
    parser = argparse.ArgumentParser(description="Generate an Anki cloze-deletion deck.")
    parser.add_argument("--cards", required=True, help="Path to cards JSON file.")
    parser.add_argument("--deck-name", required=True, help="Anki deck name (e.g. 'Black Hat Python :: Chapter 2').")
    parser.add_argument("--output", required=True, help="Output .apkg path.")
    args = parser.parse_args()

    ensure_genanki()
    import genanki

    cards_path = Path(args.cards)
    if not cards_path.exists():
        print(f"Error: cards file not found: {cards_path}", file=sys.stderr)
        sys.exit(1)

    with open(cards_path, "r", encoding="utf-8") as f:
        cards = json.load(f)

    if not isinstance(cards, list):
        print("Error: cards file must contain a JSON list.", file=sys.stderr)
        sys.exit(1)

    deck = build_deck(args.deck_name, cards)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    package = genanki.Package(deck)
    package.write_to_file(str(output_path))

    print(f"Wrote {len(deck.notes)} notes to {output_path}")


if __name__ == "__main__":
    main()
