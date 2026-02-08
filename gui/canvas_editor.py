"""Badge preview canvas with drag-and-drop field positioning and row navigation."""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from typing import List, Optional, Callable

from models.badge_config import BadgeConfig, FieldPlacement
from models.csv_data import CSVData
from utils.image_utils import compute_scale_factor, image_to_canvas, canvas_to_image


class CanvasEditor(ttk.Frame):
    """Canvas that displays the badge preview and allows dragging text fields."""

    CANVAS_MAX_W = 700
    CANVAS_MAX_H = 500

    def __init__(self, parent, config: BadgeConfig, csv_data: CSVData, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.csv_data = csv_data
        self.current_row = 0

        # Callbacks
        self.on_field_selected: Optional[Callable[[int], None]] = None
        self.on_field_moved: Optional[Callable[[int, float, float], None]] = None

        # Display state
        self._bg_image: Optional[Image.Image] = None
        self._bg_photo: Optional[ImageTk.PhotoImage] = None
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0

        # Drag state
        self._drag_field_idx: Optional[int] = None
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Tag prefix for field items
        self._field_tag_prefix = "field_"

        self._build_ui()

    def _build_ui(self):
        # Canvas
        self.canvas = tk.Canvas(
            self,
            width=self.CANVAS_MAX_W,
            height=self.CANVAS_MAX_H,
            bg="#d6d6d6",
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Row navigation bar
        nav = ttk.Frame(self)
        nav.pack(fill=tk.X, pady=(6, 0))

        self.btn_prev = ttk.Button(nav, text="\u25C0", width=3, command=self._prev_row)
        self.btn_prev.pack(side=tk.LEFT, padx=2)

        self.row_label = ttk.Label(nav, text="Row 0 of 0", font=("Segoe UI", 9))
        self.row_label.pack(side=tk.LEFT, padx=6)

        self.btn_next = ttk.Button(nav, text="\u25B6", width=3, command=self._next_row)
        self.btn_next.pack(side=tk.LEFT, padx=2)

        # Search bar
        ttk.Separator(nav, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=2)
        ttk.Label(nav, text="Search:", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(nav, textvariable=self._search_var, width=18)
        self._search_entry.pack(side=tk.LEFT, padx=2)
        self._search_entry.bind("<Return>", lambda e: self._search_next())

        self._btn_search = ttk.Button(nav, text="Find", width=5, command=self._search_next)
        self._btn_search.pack(side=tk.LEFT, padx=2)
        self._btn_search_prev = ttk.Button(nav, text="Prev", width=5, command=self._search_prev)
        self._btn_search_prev.pack(side=tk.LEFT, padx=2)

        self._search_label = ttk.Label(nav, text="", font=("Segoe UI", 8))
        self._search_label.pack(side=tk.LEFT, padx=6)

        # Search state
        self._search_results: List[int] = []
        self._search_result_idx: int = -1

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_background(self, img: Optional[Image.Image]):
        """Set the background image (PIL Image)."""
        self._bg_image = img
        self.refresh()

    def refresh(self):
        """Redraw the entire canvas: background + all field labels."""
        self.canvas.delete("all")

        cw = self.canvas.winfo_width() or self.CANVAS_MAX_W
        ch = self.canvas.winfo_height() or self.CANVAS_MAX_H

        bw = self.config.badge_width
        bh = self.config.badge_height

        self._scale = compute_scale_factor(bw, bh, cw - 20, ch - 20)
        # Center the badge in the canvas
        self._offset_x = (cw - bw * self._scale) / 2
        self._offset_y = (ch - bh * self._scale) / 2

        # Draw background
        if self._bg_image:
            display_w = int(bw * self._scale)
            display_h = int(bh * self._scale)
            resized = self._bg_image.resize((display_w, display_h), Image.LANCZOS)
            self._bg_photo = ImageTk.PhotoImage(resized)
            self.canvas.create_image(
                self._offset_x, self._offset_y,
                image=self._bg_photo, anchor=tk.NW, tags="bg"
            )
        else:
            # Draw white rectangle as badge area
            x1, y1 = self._offset_x, self._offset_y
            x2 = x1 + bw * self._scale
            y2 = y1 + bh * self._scale
            self.canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="#999999")

        # Draw badge border
        x1, y1 = self._offset_x, self._offset_y
        x2 = x1 + bw * self._scale
        y2 = y1 + bh * self._scale
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#666666", width=1, tags="border")

        # Draw fields
        for idx, fp in enumerate(self.config.fields):
            self._draw_field(idx, fp)

        self._update_row_label()

    def _draw_field(self, idx: int, fp: FieldPlacement):
        """Draw a single field text item on the canvas."""
        text = fp.csv_column
        if self.csv_data.is_loaded:
            text = self.csv_data.get_value(self.current_row, fp.csv_column)
            if not text:
                text = f"[{fp.csv_column}]"

        cx, cy = image_to_canvas(fp.x, fp.y, self._scale, self._offset_x, self._offset_y)

        # Scale font size for display
        display_size = max(8, int(fp.font_size * self._scale))

        anchor_map = {"left": tk.NW, "center": tk.N, "right": tk.NE}
        anchor = anchor_map.get(fp.alignment, tk.N)

        tag = f"{self._field_tag_prefix}{idx}"
        self.canvas.create_text(
            cx, cy,
            text=text,
            fill=fp.font_color,
            font=(fp.font_family, display_size, self._get_tk_weight(fp)),
            anchor=anchor,
            tags=(tag, "field"),
        )

    def _get_tk_weight(self, fp: FieldPlacement) -> str:
        parts = []
        if fp.bold:
            parts.append("bold")
        if fp.italic:
            parts.append("italic")
        return " ".join(parts) if parts else "normal"

    def select_field(self, idx: int):
        """Highlight a field on the canvas."""
        # Remove previous highlights
        self.canvas.delete("highlight")
        if idx < 0 or idx >= len(self.config.fields):
            return
        tag = f"{self._field_tag_prefix}{idx}"
        bbox = self.canvas.bbox(tag)
        if bbox:
            pad = 3
            self.canvas.create_rectangle(
                bbox[0] - pad, bbox[1] - pad,
                bbox[2] + pad, bbox[3] + pad,
                outline="#0078D7", width=2, tags="highlight",
            )

    # ------------------------------------------------------------------
    # Row navigation
    # ------------------------------------------------------------------

    def _prev_row(self):
        if self.current_row > 0:
            self.current_row -= 1
            self.refresh()

    def _next_row(self):
        if self.current_row < self.csv_data.row_count - 1:
            self.current_row += 1
            self.refresh()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _build_search_results(self, term: str) -> List[int]:
        """Find all row indices where any column contains the search term."""
        term_lower = term.lower()
        matches = []
        for i, row in enumerate(self.csv_data.rows):
            for val in row.values():
                if term_lower in val.lower():
                    matches.append(i)
                    break
        return matches

    def _search_next(self):
        """Jump to the next matching row."""
        term = self._search_var.get().strip()
        if not term:
            self._search_label.config(text="")
            return
        # Rebuild results each time so new data is picked up
        self._search_results = self._build_search_results(term)
        if not self._search_results:
            self._search_label.config(text="No matches")
            self._search_result_idx = -1
            return
        # Find the next result after the current row
        self._search_result_idx = -1
        for i, row_idx in enumerate(self._search_results):
            if row_idx > self.current_row:
                self._search_result_idx = i
                break
        # Wrap around if nothing found after current row
        if self._search_result_idx == -1:
            self._search_result_idx = 0
        self._goto_search_result()

    def _search_prev(self):
        """Jump to the previous matching row."""
        term = self._search_var.get().strip()
        if not term:
            self._search_label.config(text="")
            return
        self._search_results = self._build_search_results(term)
        if not self._search_results:
            self._search_label.config(text="No matches")
            self._search_result_idx = -1
            return
        # Find the previous result before the current row
        self._search_result_idx = -1
        for i in range(len(self._search_results) - 1, -1, -1):
            if self._search_results[i] < self.current_row:
                self._search_result_idx = i
                break
        # Wrap around if nothing found before current row
        if self._search_result_idx == -1:
            self._search_result_idx = len(self._search_results) - 1
        self._goto_search_result()

    def _goto_search_result(self):
        """Navigate to the current search result and update the label."""
        idx = self._search_result_idx
        results = self._search_results
        self.current_row = results[idx]
        self.refresh()
        self._search_label.config(text=f"{idx + 1} of {len(results)}")

    def _update_row_label(self):
        total = max(self.csv_data.row_count, 0)
        display = self.current_row + 1 if total > 0 else 0
        self.row_label.config(text=f"Row {display} of {total}")

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def _on_press(self, event):
        """Find which field was clicked."""
        self._drag_field_idx = None
        items = self.canvas.find_overlapping(event.x - 5, event.y - 5, event.x + 5, event.y + 5)
        for item in items:
            tags = self.canvas.gettags(item)
            for t in tags:
                if t.startswith(self._field_tag_prefix):
                    idx = int(t[len(self._field_tag_prefix):])
                    self._drag_field_idx = idx
                    self._drag_start_x = event.x
                    self._drag_start_y = event.y
                    if self.on_field_selected:
                        self.on_field_selected(idx)
                    self.select_field(idx)
                    return

    def _on_drag(self, event):
        """Move the dragged field."""
        if self._drag_field_idx is None:
            return
        idx = self._drag_field_idx
        tag = f"{self._field_tag_prefix}{idx}"

        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self.canvas.move(tag, dx, dy)
        # Move highlight too
        self.canvas.move("highlight", dx, dy)

        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_release(self, event):
        """Finalize the field position after drag."""
        if self._drag_field_idx is None:
            return
        idx = self._drag_field_idx
        tag = f"{self._field_tag_prefix}{idx}"

        # Get the canvas position of the text item
        coords = self.canvas.coords(tag)
        if coords:
            cx, cy = coords[0], coords[1]
            ix, iy = canvas_to_image(cx, cy, self._scale, self._offset_x, self._offset_y)
            # Clamp to badge bounds
            ix = max(0, min(ix, self.config.badge_width))
            iy = max(0, min(iy, self.config.badge_height))
            self.config.fields[idx].x = round(ix, 1)
            self.config.fields[idx].y = round(iy, 1)
            if self.on_field_moved:
                self.on_field_moved(idx, ix, iy)

        self._drag_field_idx = None

    def _on_canvas_resize(self, event):
        """Redraw when canvas is resized."""
        self.after(50, self.refresh)
