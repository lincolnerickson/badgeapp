"""Main application window: menu bar, toolbar, two-pane layout, status bar."""

import os
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
from typing import Optional

from models.badge_config import BadgeConfig
from models.csv_data import CSVData
from gui.canvas_editor import CanvasEditor
from gui.field_panel import FieldPanel
from gui.dialogs import ExportProgressDialog, ManualEntryDialog, PrintDialog
from export.pdf_export import export_pdf
from export.badge_renderer import render_badge


class MainWindow:
    """Top-level application window."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Convention Badge Designer")
        self.root.geometry("1060x640")
        self.root.minsize(800, 500)

        # Core state
        self.config = BadgeConfig()
        self.csv_data = CSVData()
        self._bg_image: Optional[Image.Image] = None

        self._build_menu()
        self._build_toolbar()
        self._build_main_panes()
        self._build_status_bar()

        # Wire up callbacks
        self._connect_callbacks()

        # Load font list (may take a moment on first run)
        self.root.after(100, self.field_panel.refresh_fonts)

        # Start autosave timer (every 5 minutes)
        self._schedule_autosave()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Background Image...", command=self._open_bg_image)
        file_menu.add_command(label="Open CSV...", command=self._open_csv)
        file_menu.add_command(label="Save CSV", command=self._save_csv)
        file_menu.add_command(label="Save CSV As...", command=self._save_csv_as)
        file_menu.add_separator()
        file_menu.add_command(label="Save Template...", command=self._save_template)
        file_menu.add_command(label="Load Template...", command=self._load_template)
        file_menu.add_separator()
        file_menu.add_command(label="Manual Entry...", command=self._manual_entry)
        file_menu.add_command(label="Edit Current Badge...", command=self._edit_current_badge)
        file_menu.add_command(label="Delete Current Badge", command=self._delete_current_badge)
        file_menu.add_command(label="Export PDF...", command=self._export_pdf)
        file_menu.add_command(label="Print Current Badge...", command=self._print_current_badge)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame")
        toolbar.pack(fill=tk.X, pady=(0, 1))

        pad = dict(padx=2, pady=4)
        ttk.Button(toolbar, text="Open Image", style="Toolbar.TButton",
                   command=self._open_bg_image).pack(side=tk.LEFT, **pad)
        ttk.Button(toolbar, text="Open CSV", style="Toolbar.TButton",
                   command=self._open_csv).pack(side=tk.LEFT, **pad)
        ttk.Button(toolbar, text="Save CSV", style="Toolbar.TButton",
                   command=self._save_csv).pack(side=tk.LEFT, **pad)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=4)

        ttk.Button(toolbar, text="Save Template", style="Toolbar.TButton",
                   command=self._save_template).pack(side=tk.LEFT, **pad)
        ttk.Button(toolbar, text="Load Template", style="Toolbar.TButton",
                   command=self._load_template).pack(side=tk.LEFT, **pad)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=4)

        ttk.Button(toolbar, text="Manual Entry", style="Toolbar.TButton",
                   command=self._manual_entry).pack(side=tk.LEFT, **pad)
        ttk.Button(toolbar, text="Edit Badge", style="Toolbar.TButton",
                   command=self._edit_current_badge).pack(side=tk.LEFT, **pad)
        ttk.Button(toolbar, text="Delete Badge", style="Toolbar.TButton",
                   command=self._delete_current_badge).pack(side=tk.LEFT, **pad)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=4)

        ttk.Button(toolbar, text="Export PDF", style="Accent.TButton",
                   command=self._export_pdf).pack(side=tk.LEFT, **pad)
        ttk.Button(toolbar, text="Print Badge", style="Accent.TButton",
                   command=self._print_current_badge).pack(side=tk.LEFT, **pad)

    def _build_main_panes(self):
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)

        # Canvas editor (left)
        self.canvas_editor = CanvasEditor(container, self.config, self.csv_data)
        self.canvas_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 3), pady=6)

        # Vertical separator
        ttk.Separator(container, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, pady=6)

        # Field panel (right)
        self.field_panel = FieldPanel(container, self.config, self.csv_data)
        self.field_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(3, 6), pady=6)

    def _build_status_bar(self):
        status_frame = ttk.Frame(self.root, style="Status.TFrame")
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_bar = ttk.Label(
            status_frame, text="Ready", style="Status.TLabel", padding=(8, 4)
        )
        self.status_bar.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Callbacks Wiring
    # ------------------------------------------------------------------

    def _connect_callbacks(self):
        # Canvas → Panel sync
        self.canvas_editor.on_field_selected = self._on_canvas_field_selected
        self.canvas_editor.on_field_moved = self._on_canvas_field_moved

        # Panel → Canvas sync
        self.field_panel.on_field_added = lambda fp: self.canvas_editor.refresh()
        self.field_panel.on_field_deleted = lambda idx: self.canvas_editor.refresh()
        self.field_panel.on_field_updated = lambda idx: self.canvas_editor.refresh()
        self.field_panel.on_field_selected = self._on_panel_field_selected

    def _on_canvas_field_selected(self, idx: int):
        self.field_panel.select_field(idx)

    def _on_canvas_field_moved(self, idx: int, x: float, y: float):
        self.field_panel.update_position(idx, x, y)

    def _on_panel_field_selected(self, idx: int):
        self.canvas_editor.select_field(idx)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_bg_image(self):
        path = filedialog.askopenfilename(
            title="Select Background Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image:\n{e}")
            return

        self.config.background_image_path = path
        self.config.badge_width = img.width
        self.config.badge_height = img.height
        self._bg_image = img

        self.canvas_editor.set_background(img)
        self._update_status()

    def _open_csv(self):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.csv_data.load(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load CSV:\n{e}")
            return

        self.field_panel.refresh_columns()
        self.canvas_editor.current_row = 0
        self.canvas_editor.refresh()
        self._update_status()

    def _save_csv(self):
        """Save CSV to its current file path, or prompt for a new path."""
        if not self.csv_data.is_loaded:
            messagebox.showwarning("No Data", "There is no CSV data to save.")
            return
        if not self.csv_data.file_path:
            self._save_csv_as()
            return
        try:
            self.csv_data.save(self.csv_data.file_path)
            self._set_status(f"CSV saved: {self.csv_data.file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV:\n{e}")

    def _save_csv_as(self):
        """Save CSV to a new file path chosen by the user."""
        if not self.csv_data.is_loaded:
            messagebox.showwarning("No Data", "There is no CSV data to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save CSV As",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.csv_data.save(path)
            self._set_status(f"CSV saved: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV:\n{e}")

    def _save_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Badge Template",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )
        if not path:
            return
        try:
            self.config.save_json(path)
            self._set_status(f"Template saved: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save template:\n{e}")

    def _load_template(self):
        path = filedialog.askopenfilename(
            title="Load Badge Template",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            loaded = BadgeConfig.load_json(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load template:\n{e}")
            return

        # Apply loaded config
        self.config.background_image_path = loaded.background_image_path
        self.config.badge_width = loaded.badge_width
        self.config.badge_height = loaded.badge_height
        self.config.fields = loaded.fields
        self.config.badges_per_row = loaded.badges_per_row
        self.config.badges_per_col = loaded.badges_per_col
        self.config.page_size = loaded.page_size
        self.config.margin_mm = loaded.margin_mm
        self.config.spacing_mm = loaded.spacing_mm

        # Reload background image if path is set
        if self.config.background_image_path:
            try:
                self._bg_image = Image.open(self.config.background_image_path).convert("RGBA")
                self.canvas_editor.set_background(self._bg_image)
            except Exception:
                self._bg_image = None
                self.canvas_editor.set_background(None)
        else:
            self._bg_image = None
            self.canvas_editor.set_background(None)

        self.field_panel.refresh_field_list()
        self.canvas_editor.refresh()
        self._set_status(f"Template loaded: {path}")

    def _edit_current_badge(self):
        """Open the current badge row for editing."""
        if not self.csv_data.is_loaded:
            messagebox.showwarning("No Data", "Please load a CSV file or add a manual entry first.")
            return

        row_idx = self.canvas_editor.current_row
        if row_idx < 0 or row_idx >= self.csv_data.row_count:
            return

        current_row = self.csv_data.rows[row_idx]
        # Show all CSV columns, not just the ones on the badge
        columns = list(self.csv_data.headers)

        self._edit_row_idx = row_idx
        self._edit_dialog = ManualEntryDialog(
            self.root,
            columns,
            on_preview=self._edit_preview,
            on_accept=self._edit_accept,
            on_export_pdf=self._manual_export_pdf,
            on_save_image=self._manual_save_image,
            on_close=self._edit_close,
            defaults=dict(current_row),
        )
        self._edit_dialog.title(f"Edit Badge - Row {row_idx + 1}")

    def _edit_preview(self, values):
        """Preview edited values on the canvas."""
        manual_csv = self._manual_make_csv(values)
        old_csv = self.csv_data
        self.canvas_editor.csv_data = manual_csv
        self.canvas_editor.current_row = 0
        self.canvas_editor.refresh()
        self.canvas_editor.csv_data = old_csv

    def _edit_accept(self, values):
        """Write edited values back to the existing CSV row."""
        row_idx = self._edit_row_idx
        self.csv_data.rows[row_idx].update(values)
        self.canvas_editor.current_row = row_idx
        self.canvas_editor.refresh()
        self._set_status(f"Row {row_idx + 1} updated")

    def _edit_close(self):
        """Restore canvas after closing the edit dialog."""
        self.canvas_editor.current_row = self._edit_row_idx
        self.canvas_editor.refresh()

    def _delete_current_badge(self):
        """Delete the currently displayed CSV row after confirmation."""
        if not self.csv_data.is_loaded:
            messagebox.showwarning("No Data", "There is no CSV data loaded.")
            return

        row_idx = self.canvas_editor.current_row
        if row_idx < 0 or row_idx >= self.csv_data.row_count:
            return

        # Show some identifying info in the confirmation
        row = self.csv_data.rows[row_idx]
        preview = ", ".join(f"{v}" for v in list(row.values())[:3] if v)
        if not preview:
            preview = f"Row {row_idx + 1}"

        confirm = messagebox.askyesno(
            "Delete Badge",
            f"Delete this badge entry?\n\n{preview}\n\n(Row {row_idx + 1} of {self.csv_data.row_count})",
        )
        if not confirm:
            return

        del self.csv_data.rows[row_idx]

        # Adjust current row if needed
        if self.csv_data.row_count == 0:
            self.canvas_editor.current_row = 0
        elif row_idx >= self.csv_data.row_count:
            self.canvas_editor.current_row = self.csv_data.row_count - 1

        self.canvas_editor.refresh()
        self._update_status()
        self._set_status(f"Deleted row {row_idx + 1} ({self.csv_data.row_count} rows remaining)")

    def _find_badge_number_column(self, columns):
        """Find the badge number column by looking for 'badge' in the name."""
        for col in columns:
            if "badge" in col.lower() and "num" in col.lower():
                return col
        for col in columns:
            if "badge" in col.lower():
                return col
        return None

    def _next_badge_number(self, badge_col):
        """Compute the next badge number: max existing + 1, starting at 126."""
        highest = 125
        if self.csv_data.rows and badge_col:
            for row in self.csv_data.rows:
                val = row.get(badge_col, "")
                try:
                    highest = max(highest, int(val))
                except (ValueError, TypeError):
                    pass
        return highest + 1

    def _manual_entry(self):
        if not self.config.fields:
            messagebox.showwarning("No Fields", "Please add at least one field to the badge first.")
            return

        # Start with placed field columns, then add any remaining CSV headers
        columns = list(dict.fromkeys(fp.csv_column for fp in self.config.fields))
        for h in self.csv_data.headers:
            if h not in columns:
                columns.append(h)

        # Auto-populate badge number
        defaults = {}
        badge_col = self._find_badge_number_column(columns)
        if badge_col:
            defaults[badge_col] = str(self._next_badge_number(badge_col))

        self._manual_dialog = ManualEntryDialog(
            self.root,
            columns,
            on_preview=self._manual_preview,
            on_accept=self._manual_accept,
            on_export_pdf=self._manual_export_pdf,
            on_save_image=self._manual_save_image,
            on_close=self._manual_close,
            defaults=defaults,
        )

    def _manual_make_csv(self, values):
        """Build a temporary 1-row CSVData from manual entry values."""
        manual_csv = CSVData()
        manual_csv.headers = list(values.keys())
        manual_csv.rows = [values]
        return manual_csv

    def _manual_preview(self, values):
        """Show the manually entered values on the canvas."""
        manual_csv = self._manual_make_csv(values)
        # Temporarily swap csv_data so the canvas renders from manual values
        old_csv = self.csv_data
        self.canvas_editor.csv_data = manual_csv
        self.canvas_editor.current_row = 0
        self.canvas_editor.refresh()
        # Restore so normal CSV still works after dialog closes
        self.canvas_editor.csv_data = old_csv

    def _manual_accept(self, values):
        """Add the manual entry as a row in the CSV data and close the dialog."""
        # Ensure CSV headers include all manual columns
        for col in values:
            if col not in self.csv_data.headers:
                self.csv_data.headers.append(col)
        self.csv_data.rows.append(values)

        # Jump to the newly added row
        self.canvas_editor.current_row = self.csv_data.row_count - 1
        self.canvas_editor.refresh()
        self.field_panel.refresh_columns()
        self._update_status()
        self._set_status(f"Manual entry added as row {self.csv_data.row_count}")

    def _manual_export_pdf(self, values):
        """Export a single-badge PDF from manual entry values."""
        path = filedialog.asksaveasfilename(
            title="Export Single Badge PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return
        manual_csv = self._manual_make_csv(values)
        bg = self._bg_image

        def do_export(on_progress, is_cancelled):
            export_pdf(self.config, manual_csv, path, bg, on_progress, is_cancelled)

        dialog = ExportProgressDialog(self._manual_dialog, 1, do_export)
        self._manual_dialog.wait_window(dialog)

        if not dialog._error and not dialog._cancelled:
            self._set_status(f"Single badge PDF exported: {path}")

    def _manual_save_image(self, values):
        """Save the badge as a PNG image from manual entry values."""
        path = filedialog.asksaveasfilename(
            title="Save Badge Image",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg")],
        )
        if not path:
            return
        manual_csv = self._manual_make_csv(values)
        try:
            img = render_badge(self.config, manual_csv, 0, self._bg_image)
            img.save(path)
            self._set_status(f"Badge image saved: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save image:\n{e}")

    def _manual_close(self):
        """Restore the canvas to show the loaded CSV data when dialog closes."""
        self.canvas_editor.csv_data = self.csv_data
        self.canvas_editor.current_row = 0
        self.canvas_editor.refresh()

    def _export_pdf(self):
        if not self.csv_data.is_loaded:
            messagebox.showwarning("No Data", "Please load a CSV file first.")
            return
        if not self.config.fields:
            messagebox.showwarning("No Fields", "Please add at least one field to the badge.")
            return

        path = filedialog.asksaveasfilename(
            title="Export PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return

        total = self.csv_data.row_count
        config = self.config
        csv_data = self.csv_data
        bg = self._bg_image

        def do_export(on_progress, is_cancelled):
            export_pdf(config, csv_data, path, bg, on_progress, is_cancelled)

        dialog = ExportProgressDialog(self.root, total, do_export)
        self.root.wait_window(dialog)

        if dialog._error:
            return
        if dialog._cancelled:
            self._set_status("Export cancelled.")
        else:
            self._set_status(f"PDF exported: {path}")

    def _print_current_badge(self):
        """Render the current badge and open the print dialog."""
        if not self.csv_data.is_loaded:
            messagebox.showwarning("No Data", "Please load a CSV file or add a manual entry first.")
            return
        if not self.config.fields:
            messagebox.showwarning("No Fields", "Please add at least one field to the badge.")
            return

        row = self.canvas_editor.current_row
        try:
            badge_img = render_badge(self.config, self.csv_data, row, self._bg_image)
            badge_rgb = badge_img.convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"Could not render badge:\n{e}")
            return

        # Write to a temp PDF sized to the badge
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.utils import ImageReader
            from io import BytesIO

            dpi = 300
            w_pt = self.config.badge_width / dpi * 72
            h_pt = self.config.badge_height / dpi * 72

            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=tempfile.gettempdir())
            tmp_path = tmp.name
            tmp.close()

            buf = BytesIO()
            badge_rgb.save(buf, format="PNG")
            buf.seek(0)

            c = rl_canvas.Canvas(tmp_path, pagesize=(w_pt, h_pt))
            c.drawImage(ImageReader(buf), 0, 0, w_pt, h_pt)
            c.save()
        except Exception as e:
            messagebox.showerror("Print Error", f"Could not prepare badge for printing:\n{e}")
            return

        dialog = PrintDialog(self.root, badge_rgb, tmp_path)
        self.root.wait_window(dialog)

        if dialog.printed:
            self._set_status(f"Badge printed for row {row + 1}")
            self._autosave()

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "Convention Badge Designer\n\n"
            "Design and print convention badges.\n"
            "Load a background image and CSV,\n"
            "position text fields, and export to PDF.",
        )

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _update_status(self):
        parts = []
        if self.config.background_image_path:
            parts.append(f"Image: {self.config.badge_width}x{self.config.badge_height}")
        if self.csv_data.is_loaded:
            parts.append(f"CSV: {self.csv_data.row_count} rows, {len(self.csv_data.headers)} columns")
        self.status_bar.config(text=" | ".join(parts) if parts else "Ready")

    def _set_status(self, text: str):
        self.status_bar.config(text=text)

    # ------------------------------------------------------------------
    # Autosave
    # ------------------------------------------------------------------

    def _autosave(self):
        """Save CSV to its current file path if it has one."""
        if self.csv_data.is_loaded and self.csv_data.file_path:
            try:
                self.csv_data.save(self.csv_data.file_path)
                self._set_status(f"Autosaved CSV: {self.csv_data.file_path}")
            except Exception:
                pass  # silent fail for autosave

    def _schedule_autosave(self):
        """Run autosave every 5 minutes."""
        self._autosave()
        self.root.after(5 * 60 * 1000, self._schedule_autosave)
