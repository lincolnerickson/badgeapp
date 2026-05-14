"""Renders a single badge image using Pillow."""

from PIL import Image, ImageDraw, ImageFont
from typing import Optional

from models.badge_config import BadgeConfig, FieldPlacement
from models.csv_data import CSVData
from utils.fonts import find_font_path


def resolve_field_text(fp: FieldPlacement, csv_data: CSVData, row_index: int) -> str:
    """Resolve the text to draw for a field.

    Order of resolution:
      1. `static_text` — literal text, ignores CSV.
      2. `rules` — first rule whose cell starts with 'Y' wins; trailing text appended.
      3. plain `csv_column` lookup.
    """
    if fp.static_text:
        return fp.static_text
    if not fp.rules:
        return csv_data.get_value(row_index, fp.csv_column)

    for rule in fp.rules:
        cell = csv_data.get_value(row_index, rule.column).strip()
        match_mode = getattr(rule, "match", "y") or "y"
        if match_mode == "non_dash":
            if not cell or cell == "-":
                continue
            return f"{rule.text} {cell}".strip() if rule.text else cell
        # default: "y" prefix
        if not cell or cell[0] != "Y":
            continue
        trailing = cell[1:].strip()
        return f"{rule.text} {trailing}".rstrip() if trailing else rule.text
    return ""


def _load_font(fp: FieldPlacement, size_override: Optional[int] = None) -> ImageFont.FreeTypeFont:
    """Load a PIL font for the given field placement, with fallback."""
    size = size_override or fp.font_size
    path = find_font_path(fp.font_family, fp.bold, fp.italic)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    # Fallback: try common system fonts
    for fallback in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(fallback, size)
        except (OSError, IOError):
            continue
    # Last resort: try any discovered font
    from utils.fonts import discover_fonts
    all_fonts = discover_fonts()
    if all_fonts:
        first_path = next(iter(all_fonts.values()))
        try:
            return ImageFont.truetype(first_path, size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                max_width: int) -> list:
    """Split text into lines that each fit max_width (word-boundary, greedy)."""
    words = text.split()
    if not words:
        return [text]
    lines = []
    current = [words[0]]
    for word in words[1:]:
        candidate = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    lines.append(" ".join(current))
    return lines


def _draw_field(draw: ImageDraw.ImageDraw, fp: FieldPlacement, text: str,
                dpi_scale: float = 1.0) -> None:
    """Draw a single text field onto the badge image."""
    if not text:
        return

    # Scale font size from points to pixels: points * (dpi / 72)
    pixel_size = max(1, round(fp.font_size * dpi_scale))
    font = _load_font(fp, pixel_size)
    effective_size = pixel_size
    min_size = max(1, round(8 * dpi_scale))

    anchor_map = {"left": "la", "center": "ma", "right": "ra"}
    anchor = anchor_map.get(fp.alignment, "ma")

    if fp.max_width > 0 and fp.wrap:
        # Word-wrap to fit max_width. Fall back to shrinking only if a single
        # word still doesn't fit on its own line at the chosen size.
        lines = _wrap_lines(draw, text, font, fp.max_width)
        widest = max((draw.textbbox((0, 0), ln, font=font)[2] -
                      draw.textbbox((0, 0), ln, font=font)[0]) for ln in lines)
        while widest > fp.max_width and effective_size > min_size:
            effective_size -= 1
            font = _load_font(fp, effective_size)
            lines = _wrap_lines(draw, text, font, fp.max_width)
            widest = max((draw.textbbox((0, 0), ln, font=font)[2] -
                          draw.textbbox((0, 0), ln, font=font)[0]) for ln in lines)

        ascent, descent = font.getmetrics()
        natural = ascent + descent
        multiplier = fp.line_height if fp.line_height > 0 else 1.0
        line_step = max(1, int(round(natural * multiplier)))
        y = fp.y
        for line in lines:
            draw.text((fp.x, y), line, fill=fp.font_color, font=font, anchor=anchor)
            y += line_step
        return

    # Auto-shrink if max_width is set and text overflows
    if fp.max_width > 0:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        while text_width > fp.max_width and effective_size > min_size:
            effective_size -= 1
            font = _load_font(fp, effective_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]

    draw.text(
        (fp.x, fp.y),
        text,
        fill=fp.font_color,
        font=font,
        anchor=anchor,
    )


def render_badge(
    config: BadgeConfig,
    csv_data: CSVData,
    row_index: int,
    background: Optional[Image.Image] = None,
    side: str = "front",
    back_background: Optional[Image.Image] = None,
) -> Image.Image:
    """Render a complete badge for one CSV row.

    Args:
        config: Badge template configuration.
        csv_data: Loaded CSV data.
        row_index: Which CSV row to render.
        background: Pre-loaded front background image.
        side: Which side to render ("front" or "back").
        back_background: Pre-loaded back background image.

    Returns:
        PIL Image of the rendered badge at full resolution.
    """
    size = (config.badge_width, config.badge_height)

    # Choose background based on side
    if side == "back":
        bg = back_background
        bg_path = config.back_background_image_path
    else:
        bg = background
        bg_path = config.background_image_path

    if bg:
        badge = bg.copy()
        badge = badge.resize(size, Image.LANCZOS)
    elif bg_path:
        try:
            badge = Image.open(bg_path).convert("RGBA")
            badge = badge.resize(size, Image.LANCZOS)
        except (OSError, IOError):
            badge = Image.new("RGBA", size, "white")
    else:
        badge = Image.new("RGBA", size, "white")

    draw = ImageDraw.Draw(badge)

    # Scale factor: font sizes are in points, convert to pixels at badge DPI
    dpi_scale = config.dpi / 72.0

    for fp in config.fields_for_side(side):
        text = resolve_field_text(fp, csv_data, row_index)
        _draw_field(draw, fp, text, dpi_scale)

    return badge
