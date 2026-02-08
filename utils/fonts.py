"""System font discovery (Windows + Linux)."""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PIL import ImageFont


# Cache: display name ("Arial Bold") -> file path
_font_cache: Optional[Dict[str, str]] = None

# Fonts / patterns to exclude (symbol, icon, and system UI fonts)
_BLOCKED = {
    "hololens mdl2 assets", "marlett", "segoe mdl2 assets",
    "segoe fluent icons", "segoe ui symbol", "symbol", "webdings",
    "wingdings", "wingdings 2", "wingdings 3", "bookshelf symbol 7",
    "ms outlook", "ms reference specialty", "mt extra",
    "opens___.ttf", "segmdl2.ttf", "segoeuiz.ttf",
}
_BLOCKED_SUBSTRINGS = ("mdl2", "emoji", "assets", "icons")


def _is_blocked(family: str, filename: str) -> bool:
    """Return True if this font should be excluded from the list."""
    family_lower = family.lower()
    if family_lower in _BLOCKED or filename.lower() in _BLOCKED:
        return True
    for sub in _BLOCKED_SUBSTRINGS:
        if sub in family_lower:
            return True
    return False


def discover_fonts() -> Dict[str, str]:
    """Scan system font directories for .ttf/.otf files.

    Reads the actual font family and style from TrueType metadata.
    Returns dict mapping display name -> full file path.
    """
    global _font_cache
    if _font_cache is not None:
        return _font_cache

    fonts: Dict[str, str] = {}
    font_dirs = []

    # Project-bundled fonts (fonts/ directory next to this file's parent)
    project_fonts = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
    if os.path.isdir(project_fonts):
        font_dirs.append(project_fonts)

    if sys.platform == "win32":
        # Windows system fonts
        windir = os.environ.get("WINDIR", r"C:\Windows")
        font_dirs.append(os.path.join(windir, "Fonts"))
        # User fonts (Windows 10+)
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            user_fonts = os.path.join(localappdata, "Microsoft", "Windows", "Fonts")
            if os.path.isdir(user_fonts):
                font_dirs.append(user_fonts)
    else:
        # Linux / macOS font directories
        for d in ("/usr/share/fonts", "/usr/local/share/fonts",
                  os.path.expanduser("~/.local/share/fonts"),
                  os.path.expanduser("~/.fonts")):
            if os.path.isdir(d):
                # Walk subdirectories (Linux fonts are often nested)
                for root, _, files in os.walk(d):
                    if any(f.lower().endswith((".ttf", ".otf")) for f in files):
                        font_dirs.append(root)

    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        for entry in os.scandir(font_dir):
            if not entry.is_file():
                continue
            if not entry.name.lower().endswith((".ttf", ".otf")):
                continue
            try:
                pil_font = ImageFont.truetype(entry.path, size=12)
                family, style = pil_font.getname()
            except Exception:
                continue

            if _is_blocked(family, entry.name):
                continue

            # Build display name: "Arial Bold Italic"
            if style and style.lower() != "regular":
                display = f"{family} {style}"
            else:
                display = family

            fonts[display] = entry.path

    _font_cache = dict(sorted(fonts.items()))
    return _font_cache


def find_font_path(family: str, bold: bool = False, italic: bool = False) -> Optional[str]:
    """Find the best matching font file for a family/style combination."""
    fonts = discover_fonts()

    # Build candidate display names to search for
    candidates = []
    style = ""
    if bold and italic:
        style = "Bold Italic"
    elif bold:
        style = "Bold"
    elif italic:
        style = "Italic"

    if style:
        candidates.append(f"{family} {style}")
    candidates.append(family)

    # Exact match
    for candidate in candidates:
        if candidate in fonts:
            return fonts[candidate]

    # Case-insensitive match
    lower_candidates = [c.lower() for c in candidates]
    for name, path in fonts.items():
        name_lower = name.lower()
        for candidate in lower_candidates:
            if candidate == name_lower:
                return path

    # Partial match (family name appears in font name)
    family_lower = family.lower()
    for name, path in fonts.items():
        if name.lower().startswith(family_lower):
            return path

    return None


def get_font_families() -> List[str]:
    """Return sorted list of unique font family names."""
    fonts = discover_fonts()
    suffixes = (" Bold Italic", " Bold", " Italic", " Regular", " Light",
                " Medium", " Thin", " Black", " SemiBold", " Semibold",
                " ExtraBold", " ExtraLight", " Condensed", " Demibold",
                " Oblique", " Book", " Heavy", " Narrow")
    families = set()
    for name in fonts:
        base = name
        for suffix in suffixes:
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        base = base.strip()
        if base:
            families.add(base)
    return sorted(families)
