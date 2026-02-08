"""Side panel: field list, font/size/color controls, property editor."""

import tkinter as tk
from tkinter import ttk, colorchooser
from typing import Optional, Callable, List

from models.badge_config import BadgeConfig, FieldPlacement
from models.csv_data import CSVData
from utils.fonts import get_font_families


class FieldPanel(ttk.Frame):
    """Right-side panel for managing badge fields and their properties."""

    def __init__(self, parent, config: BadgeConfig, csv_data: CSVData, **kwargs):
        super().__init__(parent, width=290, style="Panel.TFrame", **kwargs)
        self.pack_propagate(False)

        self.config = config
        self.csv_data = csv_data

        # Callbacks
        self.on_field_added: Optional[Callable[[FieldPlacement], None]] = None
        self.on_field_deleted: Optional[Callable[[int], None]] = None
        self.on_field_updated: Optional[Callable[[int], None]] = None
        self.on_field_selected: Optional[Callable[[int], None]] = None

        self._selected_idx: int = -1
        self._updating = False  # prevent feedback loops

        self._font_families: List[str] = []

        self._build_ui()

    def _make_spinner(self, parent, var: tk.StringVar, step: float, width: int = 6,
                       min_val: Optional[float] = None) -> ttk.Frame:
        """Create an Entry with up/down buttons that repeat while held."""
        frame = ttk.Frame(parent, style="Panel.TFrame")
        entry = ttk.Entry(frame, textvariable=var, width=width)
        entry.pack(side=tk.LEFT)

        btn_frame = ttk.Frame(frame, style="Panel.TFrame")
        btn_frame.pack(side=tk.LEFT, padx=(2, 0))

        def _nudge(delta):
            try:
                val = float(var.get()) + delta
                if min_val is not None:
                    val = max(min_val, val)
                var.set(str(int(val)) if step >= 1 and val == int(val) else str(round(val, 1)))
            except ValueError:
                return
            self._apply_changes()

        def _start_repeat(delta, btn):
            _nudge(delta)
            btn._repeat_id = btn.after(300, _continue_repeat, delta, btn)

        def _continue_repeat(delta, btn):
            _nudge(delta)
            btn._repeat_id = btn.after(50, _continue_repeat, delta, btn)

        def _stop_repeat(btn):
            if hasattr(btn, "_repeat_id") and btn._repeat_id:
                btn.after_cancel(btn._repeat_id)
                btn._repeat_id = None

        btn_up = tk.Button(btn_frame, text="\u25B2", width=2, padx=0, pady=0,
                           font=("Segoe UI", 5), relief="flat", bg="#e0e0e0",
                           activebackground="#c8c8c8")
        btn_up.pack(side=tk.TOP, pady=(0, 1))
        btn_up.bind("<ButtonPress-1>", lambda e: _start_repeat(step, btn_up))
        btn_up.bind("<ButtonRelease-1>", lambda e: _stop_repeat(btn_up))

        btn_dn = tk.Button(btn_frame, text="\u25BC", width=2, padx=0, pady=0,
                           font=("Segoe UI", 5), relief="flat", bg="#e0e0e0",
                           activebackground="#c8c8c8")
        btn_dn.pack(side=tk.TOP)
        btn_dn.bind("<ButtonPress-1>", lambda e: _start_repeat(-step, btn_dn))
        btn_dn.bind("<ButtonRelease-1>", lambda e: _stop_repeat(btn_dn))

        return frame

    def _build_ui(self):
        pad = dict(padx=8, pady=3)

        # --- Add Field Section ---
        add_frame = ttk.LabelFrame(self, text="Add Field", padding=(8, 6))
        add_frame.pack(fill=tk.X, **pad)

        ttk.Label(add_frame, text="CSV Column:", style="Panel.TLabel").pack(anchor=tk.W)
        self.column_var = tk.StringVar()
        self.column_combo = ttk.Combobox(
            add_frame, textvariable=self.column_var, state="readonly", width=25
        )
        self.column_combo.pack(fill=tk.X, pady=(2, 4))

        ttk.Button(add_frame, text="Add Field", command=self._add_field).pack(fill=tk.X)

        # --- Placed Fields List ---
        list_frame = ttk.LabelFrame(self, text="Placed Fields", padding=(8, 6))
        list_frame.pack(fill=tk.X, **pad)

        self.field_listbox = tk.Listbox(list_frame, height=5, exportselection=False,
                                        font=("Segoe UI", 9), relief="flat",
                                        highlightthickness=1, highlightcolor="#0078D4",
                                        selectbackground="#0078D4", selectforeground="white")
        self.field_listbox.pack(fill=tk.X, pady=(0, 4))
        self.field_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        ttk.Button(list_frame, text="Delete Field", command=self._delete_field).pack(fill=tk.X)

        # --- Properties Section ---
        props_frame = ttk.LabelFrame(self, text="Field Properties", padding=(8, 6))
        props_frame.pack(fill=tk.BOTH, expand=True, **pad)

        # X, Y with spinners
        row = ttk.Frame(props_frame, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="X:", width=4, style="Panel.TLabel").pack(side=tk.LEFT)
        self.x_var = tk.StringVar()
        self._make_spinner(row, self.x_var, step=5, width=7).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(row, text="Y:", width=3, style="Panel.TLabel").pack(side=tk.LEFT)
        self.y_var = tk.StringVar()
        self._make_spinner(row, self.y_var, step=5, width=7).pack(side=tk.LEFT)

        # Font family
        ttk.Label(props_frame, text="Font:", style="Panel.TLabel").pack(anchor=tk.W, pady=(6, 0))
        self.font_var = tk.StringVar()
        self.font_combo = ttk.Combobox(
            props_frame, textvariable=self.font_var, width=25
        )
        self.font_combo.pack(fill=tk.X, pady=2)

        # Font size + Max width
        row2 = ttk.Frame(props_frame, style="Panel.TFrame")
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="Size:", width=6, style="Panel.TLabel").pack(side=tk.LEFT)
        self.size_var = tk.StringVar()
        self._make_spinner(row2, self.size_var, step=1, width=5, min_val=1).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row2, text="Max W:", style="Panel.TLabel").pack(side=tk.LEFT)
        self.maxw_var = tk.StringVar()
        self._make_spinner(row2, self.maxw_var, step=10, width=5, min_val=0).pack(side=tk.LEFT)

        # Color
        row3 = ttk.Frame(props_frame, style="Panel.TFrame")
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="Color:", width=6, style="Panel.TLabel").pack(side=tk.LEFT)
        self.color_var = tk.StringVar(value="#000000")
        self.color_swatch = tk.Label(row3, textvariable=self.color_var, width=10,
                                     bg="#000000", fg="white", relief="flat",
                                     font=("Segoe UI", 8), padx=4, pady=2)
        self.color_swatch.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(row3, text="...", width=3, command=self._pick_color).pack(side=tk.LEFT)

        # Bold / Italic
        row4 = ttk.Frame(props_frame, style="Panel.TFrame")
        row4.pack(fill=tk.X, pady=2)
        self.bold_var = tk.BooleanVar()
        ttk.Checkbutton(row4, text="Bold", variable=self.bold_var).pack(side=tk.LEFT, padx=(0, 8))
        self.italic_var = tk.BooleanVar()
        ttk.Checkbutton(row4, text="Italic", variable=self.italic_var).pack(side=tk.LEFT)

        # Alignment
        row5 = ttk.Frame(props_frame, style="Panel.TFrame")
        row5.pack(fill=tk.X, pady=2)
        ttk.Label(row5, text="Align:", width=6, style="Panel.TLabel").pack(side=tk.LEFT)
        self.align_var = tk.StringVar(value="center")
        for val in ("left", "center", "right"):
            ttk.Radiobutton(row5, text=val.capitalize(), variable=self.align_var,
                            value=val).pack(side=tk.LEFT, padx=(0, 4))

        # Apply button
        ttk.Button(props_frame, text="Apply Changes", style="Accent.TButton",
                   command=self._apply_changes).pack(fill=tk.X, pady=(10, 2))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_columns(self):
        """Update the column dropdown from CSV headers."""
        self.column_combo["values"] = self.csv_data.headers
        if self.csv_data.headers:
            self.column_var.set(self.csv_data.headers[0])

    def refresh_field_list(self):
        """Update the placed fields listbox."""
        self.field_listbox.delete(0, tk.END)
        for fp in self.config.fields:
            self.field_listbox.insert(tk.END, fp.csv_column)
        if 0 <= self._selected_idx < len(self.config.fields):
            self.field_listbox.selection_set(self._selected_idx)

    def refresh_fonts(self):
        """Load available font families into the font dropdown."""
        self._font_families = get_font_families()
        self.font_combo["values"] = self._font_families
        if self._font_families:
            self.font_var.set(self._font_families[0])

    def select_field(self, idx: int):
        """Select a field by index and populate the property editors."""
        self._selected_idx = idx
        self.field_listbox.selection_clear(0, tk.END)
        if 0 <= idx < len(self.config.fields):
            self.field_listbox.selection_set(idx)
            self._load_field_properties(self.config.fields[idx])
        if self.on_field_selected:
            self.on_field_selected(idx)

    def update_position(self, idx: int, x: float, y: float):
        """Update X/Y entries after a canvas drag (avoids feedback loop)."""
        if idx == self._selected_idx:
            self._updating = True
            self.x_var.set(str(round(x, 1)))
            self.y_var.set(str(round(y, 1)))
            self._updating = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_field_properties(self, fp: FieldPlacement):
        """Populate property editors from a FieldPlacement."""
        self._updating = True
        self.x_var.set(str(round(fp.x, 1)))
        self.y_var.set(str(round(fp.y, 1)))
        self.font_var.set(fp.font_family)
        self.size_var.set(str(fp.font_size))
        self.maxw_var.set(str(fp.max_width))
        self.color_var.set(fp.font_color)
        self.color_swatch.config(bg=fp.font_color)
        try:
            r, g, b = int(fp.font_color[1:3], 16), int(fp.font_color[3:5], 16), int(fp.font_color[5:7], 16)
            fg = "white" if (r * 0.299 + g * 0.587 + b * 0.114) < 128 else "black"
            self.color_swatch.config(fg=fg)
        except (ValueError, IndexError):
            pass
        self.bold_var.set(fp.bold)
        self.italic_var.set(fp.italic)
        self.align_var.set(fp.alignment)
        self._updating = False

    def _add_field(self):
        col = self.column_var.get()
        if not col:
            return
        fp = FieldPlacement(
            csv_column=col,
            x=self.config.badge_width / 2,
            y=self.config.badge_height / 2,
            font_family=self.font_var.get() or "Arial",
            font_size=24,
        )
        self.config.fields.append(fp)
        self.refresh_field_list()
        idx = len(self.config.fields) - 1
        self.select_field(idx)
        if self.on_field_added:
            self.on_field_added(fp)

    def _delete_field(self):
        if 0 <= self._selected_idx < len(self.config.fields):
            idx = self._selected_idx
            del self.config.fields[idx]
            self._selected_idx = -1
            self.refresh_field_list()
            if self.on_field_deleted:
                self.on_field_deleted(idx)

    def _apply_changes(self):
        """Write property editor values back to the selected FieldPlacement."""
        if self._updating:
            return
        idx = self._selected_idx
        if idx < 0 or idx >= len(self.config.fields):
            return

        fp = self.config.fields[idx]
        try:
            fp.x = float(self.x_var.get())
        except ValueError:
            pass
        try:
            fp.y = float(self.y_var.get())
        except ValueError:
            pass
        fp.font_family = self.font_var.get() or fp.font_family
        try:
            fp.font_size = int(self.size_var.get())
        except ValueError:
            pass
        try:
            fp.max_width = int(self.maxw_var.get())
        except ValueError:
            pass
        fp.font_color = self.color_var.get() or fp.font_color
        fp.bold = self.bold_var.get()
        fp.italic = self.italic_var.get()
        fp.alignment = self.align_var.get()

        if self.on_field_updated:
            self.on_field_updated(idx)

    def _pick_color(self):
        color = colorchooser.askcolor(
            initialcolor=self.color_var.get(), title="Choose text color"
        )
        if color[1]:
            self.color_var.set(color[1])
            self.color_swatch.config(bg=color[1])

    def _on_listbox_select(self, event):
        sel = self.field_listbox.curselection()
        if sel:
            idx = sel[0]
            self._selected_idx = idx
            self._load_field_properties(self.config.fields[idx])
            if self.on_field_selected:
                self.on_field_selected(idx)
