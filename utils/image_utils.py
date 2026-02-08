"""Scale factor and coordinate conversion helpers for canvas display."""

from typing import Tuple


def compute_scale_factor(
    image_width: int,
    image_height: int,
    canvas_width: int,
    canvas_height: int,
) -> float:
    """Compute uniform scale factor to fit image within canvas bounds."""
    if image_width <= 0 or image_height <= 0:
        return 1.0
    scale_x = canvas_width / image_width
    scale_y = canvas_height / image_height
    return min(scale_x, scale_y)


def image_to_canvas(
    x: float, y: float, scale: float, offset_x: float = 0, offset_y: float = 0
) -> Tuple[float, float]:
    """Convert image coordinates to canvas coordinates."""
    return (x * scale + offset_x, y * scale + offset_y)


def canvas_to_image(
    cx: float, cy: float, scale: float, offset_x: float = 0, offset_y: float = 0
) -> Tuple[float, float]:
    """Convert canvas coordinates back to image coordinates."""
    if scale == 0:
        return (0.0, 0.0)
    return ((cx - offset_x) / scale, (cy - offset_y) / scale)
