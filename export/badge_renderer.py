"""Renders a single badge image using Pillow."""

from PIL import Image, ImageDraw, ImageFont
from typing import Optional

from models.badge_config import BadgeConfig, FieldPlacement
from models.csv_data import CSVData
from utils.fonts import find_font_path


def _load_font(fp: FieldPlacement, size_override: Optional[int] = None) -> ImageFont.FreeTypeFont:
    """Load a PIL font for the given field placement, with fallback."""
    size = size_override or fp.font_size
    path = find_font_path(fp.font_family, fp.bold, fp.italic)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    # Fallback: try Arial directly
    try:
        return ImageFont.truetype("arial.ttf", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def _draw_field(draw: ImageDraw.ImageDraw, fp: FieldPlacement, text: str) -> None:
    """Draw a single text field onto the badge image."""
    if not text:
        return

    font = _load_font(fp)
    effective_size = fp.font_size

    # Auto-shrink if max_width is set and text overflows
    if fp.max_width > 0:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        while text_width > fp.max_width and effective_size > 8:
            effective_size -= 1
            font = _load_font(fp, effective_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]

    anchor_map = {"left": "lt", "center": "mt", "right": "rt"}
    anchor = anchor_map.get(fp.alignment, "mt")

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
) -> Image.Image:
    """Render a complete badge for one CSV row.

    Args:
        config: Badge template configuration.
        csv_data: Loaded CSV data.
        row_index: Which CSV row to render.
        background: Pre-loaded background image (avoids reloading per badge).

    Returns:
        PIL Image of the rendered badge at full resolution.
    """
    # Start with background or blank
    if background:
        badge = background.copy()
        badge = badge.resize((config.badge_width, config.badge_height), Image.LANCZOS)
    elif config.background_image_path:
        try:
            badge = Image.open(config.background_image_path).convert("RGBA")
            badge = badge.resize((config.badge_width, config.badge_height), Image.LANCZOS)
        except (OSError, IOError):
            badge = Image.new("RGBA", (config.badge_width, config.badge_height), "white")
    else:
        badge = Image.new("RGBA", (config.badge_width, config.badge_height), "white")

    draw = ImageDraw.Draw(badge)

    for fp in config.fields:
        text = csv_data.get_value(row_index, fp.csv_column)
        _draw_field(draw, fp, text)

    return badge
