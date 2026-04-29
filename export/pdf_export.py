"""PDF generation: grid layout calculation + PDF assembly with ReportLab."""

from io import BytesIO
from typing import Optional, Callable

from PIL import Image
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from models.badge_config import BadgeConfig
from models.csv_data import CSVData
from export.badge_renderer import render_badge


def _get_page_size(name: str):
    """Return ReportLab page size tuple."""
    return A4 if name.lower() == "a4" else letter


def _place_badge(c, badge_img, col, row_on_page, margin, cell_w, cell_h,
                 draw_w, draw_h, spacing, page_h):
    """Draw a rendered badge image at the given grid position on the PDF."""
    # Composite onto white to avoid transparent areas rendering as black
    if badge_img.mode == "RGBA":
        white_bg = Image.new("RGBA", badge_img.size, (255, 255, 255, 255))
        white_bg.paste(badge_img, mask=badge_img)
        badge_img = white_bg.convert("RGB")
    else:
        badge_img = badge_img.convert("RGB")
    img_buffer = BytesIO()
    badge_img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    x = margin + col * (cell_w + spacing) + (cell_w - draw_w) / 2
    y = page_h - margin - (row_on_page + 1) * cell_h - row_on_page * spacing + (cell_h - draw_h) / 2

    c.drawImage(ImageReader(img_buffer), x, y, draw_w, draw_h)


def export_pdf(
    config: BadgeConfig,
    csv_data: CSVData,
    output_path: str,
    background: Optional[Image.Image] = None,
    back_background: Optional[Image.Image] = None,
    on_progress: Optional[Callable[[int], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> None:
    """Export all CSV rows as badges into a multi-page PDF.

    Badges are arranged in a grid on each page. Each badge is rendered
    at full resolution with Pillow, then placed onto the PDF with ReportLab.

    When back content exists, pages are interleaved (front page, back page)
    with back badges horizontally mirrored for duplex printing alignment.
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
    total_rows = csv_data.row_count
    has_back = config.has_back or back_background is not None

    c = rl_canvas.Canvas(output_path, pagesize=(page_w, page_h))
    progress_count = 0

    for page_start in range(0, total_rows, badges_per_page):
        if is_cancelled and is_cancelled():
            break

        page_end = min(page_start + badges_per_page, total_rows)

        # --- Front page ---
        for i in range(page_start, page_end):
            if is_cancelled and is_cancelled():
                break
            badge_img = render_badge(config, csv_data, i, background, side="front")
            page_idx = i - page_start
            col = page_idx % cols
            row_on_page = page_idx // cols
            _place_badge(c, badge_img, col, row_on_page, margin, cell_w, cell_h,
                         draw_w, draw_h, spacing, page_h)
            progress_count += 1
            if on_progress:
                on_progress(progress_count)

        if has_back:
            # Start a new page for backs
            c.showPage()

            # --- Back page (horizontally mirrored for duplex) ---
            for i in range(page_start, page_end):
                if is_cancelled and is_cancelled():
                    break
                badge_img = render_badge(config, csv_data, i, background,
                                         side="back", back_background=back_background)
                page_idx = i - page_start
                col = page_idx % cols
                row_on_page = page_idx // cols
                mirrored_col = cols - 1 - col
                _place_badge(c, badge_img, mirrored_col, row_on_page, margin, cell_w, cell_h,
                             draw_w, draw_h, spacing, page_h)
                progress_count += 1
                if on_progress:
                    on_progress(progress_count)

        # Start new page if there are more badges
        if page_end < total_rows:
            c.showPage()

    c.save()
