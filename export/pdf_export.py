"""PDF generation: grid layout calculation + PDF assembly with ReportLab."""

from io import BytesIO
from typing import Optional, Callable

from PIL import Image
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from models.badge_config import BadgeConfig
from models.csv_data import CSVData
from export.badge_renderer import render_badge


def _get_page_size(name: str):
    """Return ReportLab page size tuple."""
    return A4 if name.lower() == "a4" else letter


def export_pdf(
    config: BadgeConfig,
    csv_data: CSVData,
    output_path: str,
    background: Optional[Image.Image] = None,
    on_progress: Optional[Callable[[int], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> None:
    """Export all CSV rows as badges into a multi-page PDF.

    Badges are arranged in a grid on each page. Each badge is rendered
    at full resolution with Pillow, then placed onto the PDF with ReportLab.
    """
    page_w, page_h = _get_page_size(config.page_size)
    margin = config.margin_mm * mm
    spacing = config.spacing_mm * mm

    # Usable area
    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin

    cols = config.badges_per_row
    rows = config.badges_per_col

    # Cell size (badge + spacing)
    cell_w = (usable_w - (cols - 1) * spacing) / cols
    cell_h = (usable_h - (rows - 1) * spacing) / rows

    # Scale badge to fit cell while preserving aspect ratio
    badge_aspect = config.badge_width / max(config.badge_height, 1)
    cell_aspect = cell_w / max(cell_h, 1)

    if badge_aspect > cell_aspect:
        draw_w = cell_w
        draw_h = cell_w / badge_aspect
    else:
        draw_h = cell_h
        draw_w = cell_h * badge_aspect

    badges_per_page = cols * rows

    c = rl_canvas.Canvas(output_path, pagesize=(page_w, page_h))

    total_rows = csv_data.row_count
    for i in range(total_rows):
        if is_cancelled and is_cancelled():
            break

        # Render badge image
        badge_img = render_badge(config, csv_data, i, background)
        badge_img = badge_img.convert("RGB")

        # Convert PIL Image to ReportLab-compatible format
        img_buffer = BytesIO()
        badge_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Position on page
        page_idx = i % badges_per_page
        col = page_idx % cols
        row_on_page = page_idx // cols

        # ReportLab origin is bottom-left, so invert Y
        x = margin + col * (cell_w + spacing) + (cell_w - draw_w) / 2
        y = page_h - margin - (row_on_page + 1) * cell_h - row_on_page * spacing + (cell_h - draw_h) / 2

        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(img_buffer), x, y, draw_w, draw_h)

        # New page if this page is full (and there are more badges)
        if page_idx == badges_per_page - 1 and i < total_rows - 1:
            c.showPage()

        if on_progress:
            on_progress(i + 1)

    c.save()
