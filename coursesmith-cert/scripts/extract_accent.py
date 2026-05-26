"""Extract a neon-treated accent palette from a book cover image.

Public surface:
    extract_from_pdf(pdf_path) -> AccentPalette

Returns dark and light variants for the same cover-derived hue.

Falls back to Coursesmith neon green if no vivid colour cluster is found in
either the top-25% banner zone or the full cover.

Algorithm in brief:
  1. Render the first page of the PDF to an image (pdfimages, fall back to
     pdftoppm).
  2. Look for a vivid colour cluster in the top 25% (most tech books have a
     hero-coloured title bar); if none, scan the whole cover.
  3. Discard near-greys and near-blacks/whites (saturation < 0.25, value
     < 0.15 or > 0.90).
  4. Take the winning colour's hue. Discard its lightness and chroma.
  5. Construct the dark variant at OKLCH L=0.72, max-ish chroma.
  6. Construct the light variant at OKLCH L=0.45, max-ish chroma.
  7. Convert back to sRGB hex; derive dim/glow rgba strings.

No external dependencies beyond Pillow. OKLCH conversion is implemented
inline to avoid pulling in colour-science libraries.
"""

from __future__ import annotations

import colorsys
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "Pillow is required. Install with: pip install Pillow"
    )


# Default accent when extraction fails. Coursesmith neon green.
_DEFAULT_HUE_OKLCH = 145.0  # h component of #7cf07c in OKLCH

# Tunable thresholds
_SATURATION_FLOOR = 0.25
_VALUE_FLOOR = 0.15
_VALUE_CEIL = 0.90
_TOP_BAND_FRACTION = 0.25
_QUANTIZE_COLOURS = 16
_RESIZE_WIDTH = 200

# Neon-zone lightness/chroma targets
_L_DARK = 0.72
_L_LIGHT = 0.45
_C_TARGET = 0.20
_C_RETRY = 0.18


@dataclass(frozen=True)
class AccentPalette:
    """Dark and light variants of one cover-derived hue."""

    dark_hex: str
    dark_dim: str
    dark_glow: str
    light_hex: str
    light_dim: str
    light_glow: str
    source: str  # "cover" or "default"

    def to_substitutions(self) -> dict[str, str]:
        """Token map for template substitution."""
        return {
            "{{ACCENT_COLOR}}": self.dark_hex,
            "{{ACCENT_DIM}}": self.dark_dim,
            "{{ACCENT_GLOW}}": self.dark_glow,
            "{{ACCENT_COLOR_LIGHT}}": self.light_hex,
            "{{ACCENT_DIM_LIGHT}}": self.light_dim,
            "{{ACCENT_GLOW_LIGHT}}": self.light_glow,
        }


# ----------------------------------------------------------------------------
# Cover extraction
# ----------------------------------------------------------------------------


def _extract_cover_via_pdfimages(pdf_path: str, out_dir: str) -> Optional[str]:
    """Try `pdfimages -f 1 -l 1`. Returns the largest extracted PNG path or
    None on failure."""
    if not shutil.which("pdfimages"):
        return None
    prefix = os.path.join(out_dir, "cover")
    try:
        subprocess.run(
            ["pdfimages", "-f", "1", "-l", "1", "-png", pdf_path, prefix],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    candidates = list(Path(out_dir).glob("cover-*.png"))
    if not candidates:
        return None
    # Largest by pixel count.
    def pixel_count(p: Path) -> int:
        try:
            with Image.open(p) as im:
                return im.width * im.height
        except Exception:
            return 0
    candidates.sort(key=pixel_count, reverse=True)
    if pixel_count(candidates[0]) == 0:
        return None
    return str(candidates[0])


def _extract_cover_via_pdftoppm(pdf_path: str, out_dir: str) -> Optional[str]:
    """Fall back: render page 1 with pdftoppm at 100 DPI."""
    if not shutil.which("pdftoppm"):
        return None
    prefix = os.path.join(out_dir, "page1")
    try:
        subprocess.run(
            ["pdftoppm", "-f", "1", "-l", "1", "-png", "-r", "100",
             pdf_path, prefix],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    candidates = list(Path(out_dir).glob("page1-*.png"))
    if not candidates:
        return None
    return str(candidates[0])


def _load_cover(pdf_path: str, work_dir: str) -> Optional[Image.Image]:
    """Try pdfimages first, fall back to pdftoppm."""
    path = _extract_cover_via_pdfimages(pdf_path, work_dir)
    if path is None:
        path = _extract_cover_via_pdftoppm(pdf_path, work_dir)
    if path is None:
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Vivid-cluster detection
# ----------------------------------------------------------------------------


def _find_vivid_cluster(image: Image.Image) -> Optional[tuple[int, int, int]]:
    """Return the most-common RGB triplet that passes the saturation/value
    filter, or None if no cluster qualifies."""
    # Resize narrow for speed; keep aspect.
    if image.width > _RESIZE_WIDTH:
        ratio = _RESIZE_WIDTH / image.width
        new_size = (_RESIZE_WIDTH, max(1, int(image.height * ratio)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    palette_img = image.quantize(
        colors=_QUANTIZE_COLOURS,
        method=Image.Quantize.MEDIANCUT,
    )
    palette = palette_img.getpalette() or []
    # Pixel histogram for the quantised palette.
    counts = palette_img.getcolors()  # list of (count, palette_index)
    if not counts:
        return None
    # Sort by count, descending.
    counts.sort(key=lambda c: c[0], reverse=True)

    for _count, idx in counts:
        r = palette[idx * 3]
        g = palette[idx * 3 + 1]
        b = palette[idx * 3 + 2]
        # HSV filter.
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < _SATURATION_FLOOR:
            continue
        if v < _VALUE_FLOOR or v > _VALUE_CEIL:
            continue
        return (r, g, b)
    return None


def _two_pass_dominant(image: Image.Image) -> Optional[tuple[int, int, int]]:
    """Try the top-band first, fall back to the full cover."""
    w, h = image.size
    if h > 8:
        band = image.crop((0, 0, w, max(1, int(h * _TOP_BAND_FRACTION))))
        rgb = _find_vivid_cluster(band)
        if rgb is not None:
            return rgb
    return _find_vivid_cluster(image)


# ----------------------------------------------------------------------------
# Colour-space conversions
# ----------------------------------------------------------------------------


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    v = c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return v * 255.0


def _rgb_to_oklab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """sRGB (0..255) → OKLab."""
    lr = _srgb_to_linear(r)
    lg = _srgb_to_linear(g)
    lb = _srgb_to_linear(b)
    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb
    l_ = l ** (1 / 3) if l >= 0 else -((-l) ** (1 / 3))
    m_ = m ** (1 / 3) if m >= 0 else -((-m) ** (1 / 3))
    s_ = s ** (1 / 3) if s >= 0 else -((-s) ** (1 / 3))
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return (L, a, b_)


def _oklab_to_rgb(L: float, a: float, b: float) -> tuple[int, int, int]:
    """OKLab → sRGB (0..255), clipped per channel."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3
    lr =  4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    r = int(round(max(0.0, min(255.0, _linear_to_srgb(lr)))))
    g = int(round(max(0.0, min(255.0, _linear_to_srgb(lg)))))
    b_ = int(round(max(0.0, min(255.0, _linear_to_srgb(lb)))))
    return (r, g, b_)


def _oklab_to_oklch(L: float, a: float, b: float) -> tuple[float, float, float]:
    C = math.sqrt(a * a + b * b)
    h = math.degrees(math.atan2(b, a)) % 360
    return (L, C, h)


def _oklch_to_oklab(L: float, C: float, h: float) -> tuple[float, float, float]:
    rad = math.radians(h)
    return (L, C * math.cos(rad), C * math.sin(rad))


def _extract_hue(r: int, g: int, b: int) -> float:
    """Return just the OKLCH hue of the given sRGB triplet."""
    L, a, b_ = _rgb_to_oklab(r, g, b)
    _, _, h = _oklab_to_oklch(L, a, b_)
    return h


# ----------------------------------------------------------------------------
# Neonification
# ----------------------------------------------------------------------------


def _channels_clipped(r: int, g: int, b: int, raw_L: float, raw_a: float,
                      raw_b: float) -> bool:
    """Detect if any channel was clipped substantially (>5/255 from the
    unclipped value). Recomputes the unclipped linear values."""
    l_ = raw_L + 0.3963377774 * raw_a + 0.2158037573 * raw_b
    m_ = raw_L - 0.1055613458 * raw_a - 0.0638541728 * raw_b
    s_ = raw_L - 0.0894841775 * raw_a - 1.2914855480 * raw_b
    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3
    lr =  4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    raw = (_linear_to_srgb(lr), _linear_to_srgb(lg), _linear_to_srgb(lb))
    for raw_c, clip_c in zip(raw, (r, g, b)):
        if raw_c < -5 or raw_c > 260:
            if abs(raw_c - clip_c) > 5:
                return True
    return False


def _neonify(hue: float, L: float) -> tuple[int, int, int]:
    """Build an sRGB triplet at the given OKLCH lightness and target chroma,
    preserving the input hue. If the result clips substantially, retry once
    at a lower chroma."""
    for C in (_C_TARGET, _C_RETRY):
        Lab = _oklch_to_oklab(L, C, hue)
        rgb = _oklab_to_rgb(*Lab)
        if not _channels_clipped(*rgb, *Lab):
            return rgb
    return rgb  # accept whatever we got


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _rgba(rgb: tuple[int, int, int], alpha: float) -> str:
    return "rgba({}, {}, {}, {:.2f})".format(rgb[0], rgb[1], rgb[2], alpha)


# ----------------------------------------------------------------------------
# Public surface
# ----------------------------------------------------------------------------


def _default_palette() -> AccentPalette:
    """Coursesmith neon green, for the no-cluster-found case."""
    dark = (124, 240, 124)
    light_rgb = _neonify(_DEFAULT_HUE_OKLCH, _L_LIGHT)
    return AccentPalette(
        dark_hex=_hex(dark),
        dark_dim=_rgba(dark, 0.15),
        dark_glow=_rgba(dark, 0.40),
        light_hex=_hex(light_rgb),
        light_dim=_rgba(light_rgb, 0.12),
        light_glow=_rgba(light_rgb, 0.25),
        source="default",
    )


def palette_from_hex(accent_hex: str) -> AccentPalette:
    """Build a palette from a user-supplied hex override. Skips extraction,
    treats the supplied hex as the dark variant, derives the light variant
    by re-neonifying at L=0.45."""
    accent_hex = accent_hex.lstrip("#")
    if len(accent_hex) != 6:
        raise ValueError(f"accent must be a #rrggbb hex string, got {accent_hex!r}")
    r = int(accent_hex[0:2], 16)
    g = int(accent_hex[2:4], 16)
    b = int(accent_hex[4:6], 16)
    hue = _extract_hue(r, g, b)
    dark_rgb = (r, g, b)  # use exactly what the user gave us
    light_rgb = _neonify(hue, _L_LIGHT)
    return AccentPalette(
        dark_hex=_hex(dark_rgb),
        dark_dim=_rgba(dark_rgb, 0.15),
        dark_glow=_rgba(dark_rgb, 0.40),
        light_hex=_hex(light_rgb),
        light_dim=_rgba(light_rgb, 0.12),
        light_glow=_rgba(light_rgb, 0.25),
        source="override",
    )


def extract_from_pdf(pdf_path: str) -> AccentPalette:
    """Derive a dark+light accent palette from the book's cover.

    Returns the default Coursesmith green palette if extraction yields no
    vivid colour cluster."""
    with tempfile.TemporaryDirectory() as work_dir:
        cover = _load_cover(pdf_path, work_dir)
        if cover is None:
            return _default_palette()
        rgb = _two_pass_dominant(cover)
        if rgb is None:
            return _default_palette()

    hue = _extract_hue(*rgb)
    dark_rgb = _neonify(hue, _L_DARK)
    light_rgb = _neonify(hue, _L_LIGHT)
    return AccentPalette(
        dark_hex=_hex(dark_rgb),
        dark_dim=_rgba(dark_rgb, 0.15),
        dark_glow=_rgba(dark_rgb, 0.40),
        light_hex=_hex(light_rgb),
        light_dim=_rgba(light_rgb, 0.12),
        light_glow=_rgba(light_rgb, 0.25),
        source="cover",
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: extract_accent.py <pdf-path>", file=sys.stderr)
        sys.exit(2)
    p = extract_from_pdf(sys.argv[1])
    print(f"source: {p.source}")
    print(f"dark:  {p.dark_hex}  dim={p.dark_dim}  glow={p.dark_glow}")
    print(f"light: {p.light_hex}  dim={p.light_dim}  glow={p.light_glow}")
