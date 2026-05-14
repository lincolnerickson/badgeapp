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


def _place_badge(c, badge_img, col, row_on_page, x_start, y_top,
                 draw_w, draw_h, spacing):
    """Draw a rendered badge image at the given grid position on the PDF.

    `x_start` is the PDF x coordinate of the left edge of column 0.
    `y_top` is the PDF y coordinate of the top edge of row 0.
    Badges are placed adjacent with exactly `spacing` between them.
    """
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

    x = x_start + col * (draw_w + spacing)
    y = y_top - draw_h - row_on_page * (draw_h + spacing)

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

    # Draw each badge at its configured physical size (badge_width pixels /
    # config.dpi inches * 72 points-per-inch). Lay them out adjacent with
    # exactly `spacing` between, and scale the whole grid down if it doesn't
    # fit in the usable area (preserves aspect ratio).
    target_w = config.badge_width / max(config.dpi, 1) * 72.0
    target_h = config.badge_height / max(config.dpi, 1) * 72.0

    grid_w = cols * target_w + max(0, cols - 1) * spacing
    grid_h = rows * target_h + max(0, rows - 1) * spacing
    scale = min(1.0, usable_w / max(grid_w, 1), usable_h / max(grid_h, 1))
    draw_w = target_w * scale
    draw_h = target_h * scale

    # Center the whole grid on the page so duplex front/back stay aligned.
    final_grid_w = cols * draw_w + max(0, cols - 1) * spacing
    final_grid_h = rows * draw_h + max(0, rows - 1) * spacing
    x_start = (page_w - final_grid_w) / 2
    y_top = page_h - (page_h - final_grid_h) / 2

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
            _place_badge(c, badge_img, col, row_on_page, x_start, y_top,
                         draw_w, draw_h, spacing)
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
                _place_badge(c, badge_img, mirrored_col, row_on_page, x_start, y_top,
                             draw_w, draw_h, spacing)
                progress_count += 1
                if on_progress:
                    on_progress(progress_count)

        # Start new page if there are more badges
        if page_end < total_rows:
            c.showPage()

    c.save()
