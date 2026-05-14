"""Side panel: field list, font/size/color controls, property editor."""

import tkinter as tk
from tkinter import ttk, colorchooser
from typing import Optional, Callable, List

from models.badge_config import BadgeConfig, FieldPlacement, ConditionalRule
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
        self.on_badge_size_changed: Optional[Callable[[int, int], None]] = None

        self._selected_idx: int = -1  # global index into config.fields
        self._updating = False  # prevent feedback loops
        self._current_side: str = "front"
        self._listbox_to_field_idx: List[int] = []  # maps listbox row → global field index

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

        # --- Scrollable container ---
        # Tk Frames don't scroll on their own; put everything in a Canvas with
        # a Scrollbar and pack the real sections into an inner frame.
        outer_canvas = tk.Canvas(self, highlightthickness=0,
                                  background=self._lookup_panel_bg())
        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                   command=outer_canvas.yview)
        outer_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        outer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = ttk.Frame(outer_canvas, style="Panel.TFrame")
        inner_window = outer_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _sync_scrollregion(_event=None):
            outer_canvas.configure(scrollregion=outer_canvas.bbox("all"))
            outer_canvas.itemconfigure(inner_window,
                                        width=outer_canvas.winfo_width())

        inner.bind("<Configure>", _sync_scrollregion)
        outer_canvas.bind("<Configure>", _sync_scrollregion)

        # Mouse wheel scrolling while the cursor is over the panel.
        def _on_mousewheel(event):
            outer_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        outer_canvas.bind_all("<MouseWheel>", lambda e: _on_mousewheel(e)
                              if str(e.widget).startswith(str(outer_canvas))
                              else None)

        self._scroll_canvas = outer_canvas
        self._scroll_inner = inner

        # --- Add Field Section ---
        add_frame = ttk.LabelFrame(inner, text="Add Field", padding=(8, 6))
        add_frame.pack(fill=tk.X, **pad)

        ttk.Label(add_frame, text="CSV Column:", style="Panel.TLabel").pack(anchor=tk.W)
        self.column_var = tk.StringVar()
        self.column_combo = ttk.Combobox(
            add_frame, textvariable=self.column_var, state="readonly", width=25
        )
        self.column_combo.pack(fill=tk.X, pady=(2, 4))

        ttk.Button(add_frame, text="Add Field", command=self._add_field).pack(fill=tk.X)
        ttk.Button(add_frame, text="+ Static Text",
                   command=self._add_static_text).pack(fill=tk.X, pady=(2, 0))

        # --- Placed Fields List ---
        list_frame = ttk.LabelFrame(inner, text="Placed Fields", padding=(8, 6))
        list_frame.pack(fill=tk.X, **pad)

        self.field_listbox = tk.Listbox(list_frame, height=5, exportselection=False,
                                        font=("Segoe UI", 9), relief="flat",
                                        highlightthickness=1, highlightcolor="#0078D4",
                                        selectbackground="#0078D4", selectforeground="white")
        self.field_listbox.pack(fill=tk.X, pady=(0, 4))
        self.field_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        ttk.Button(list_frame, text="Delete Field", command=self._delete_field).pack(fill=tk.X)

        # --- Properties Section ---
        props_frame = ttk.LabelFrame(inner, text="Field Properties", padding=(8, 6))
        props_frame.pack(fill=tk.BOTH, expand=True, **pad)

        # Static text
        row_static = ttk.Frame(props_frame, style="Panel.TFrame")
        row_static.pack(fill=tk.X, pady=2)
        ttk.Label(row_static, text="Text:", width=6, style="Panel.TLabel").pack(side=tk.LEFT)
        self.static_text_var = tk.StringVar()
        ttk.Entry(row_static, textvariable=self.static_text_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

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
        self._make_spinner(row2, self.maxw_var, step=10, width=5, min_val=0).pack(side=tk.LEFT, padx=(0, 8))

        self.wrap_var = tk.BooleanVar()
        ttk.Checkbutton(row2, text="Wrap", variable=self.wrap_var).pack(side=tk.LEFT)

        # Line height (multiplier of natural line height)
        row_lh = ttk.Frame(props_frame, style="Panel.TFrame")
        row_lh.pack(fill=tk.X, pady=2)
        ttk.Label(row_lh, text="Line H:", width=6, style="Panel.TLabel").pack(side=tk.LEFT)
        self.line_height_var = tk.StringVar(value="1.0")
        ttk.Entry(row_lh, textvariable=self.line_height_var, width=6).pack(side=tk.LEFT)

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

        # Conditional rules
        rules_header = ttk.Frame(props_frame, style="Panel.TFrame")
        rules_header.pack(fill=tk.X, pady=(8, 2))
        ttk.Label(rules_header, text="Conditional Rules:", style="Panel.TLabel").pack(side=tk.LEFT)
        ttk.Button(rules_header, text="+ Rule", width=7,
                   command=self._add_rule_row).pack(side=tk.RIGHT)

        ttk.Label(props_frame,
                  text="If column starts with 'Y', render text + trailing.",
                  style="Panel.TLabel",
                  font=("Segoe UI", 8),
                  wraplength=260,
                  foreground="#666").pack(anchor=tk.W, pady=(0, 2))

        self.rules_frame = ttk.Frame(props_frame, style="Panel.TFrame")
        self.rules_frame.pack(fill=tk.X, pady=(0, 4))
        self._rule_rows: List[dict] = []  # each: {frame, column_var, text_var}

        # Apply button
        ttk.Button(props_frame, text="Apply Changes", style="Accent.TButton",
                   command=self._apply_changes).pack(fill=tk.X, pady=(10, 2))

        # --- Badge Size Section ---
        size_frame = ttk.LabelFrame(inner, text="Badge Size", padding=(8, 6))
        size_frame.pack(fill=tk.X, **pad)

        row_w = ttk.Frame(size_frame, style="Panel.TFrame")
        row_w.pack(fill=tk.X, pady=2)
        ttk.Label(row_w, text="Width (in):", width=10, style="Panel.TLabel").pack(side=tk.LEFT)
        self.badge_w_in_var = tk.StringVar(value="3.5")
        ttk.Entry(row_w, textvariable=self.badge_w_in_var, width=8).pack(side=tk.LEFT)

        row_h = ttk.Frame(size_frame, style="Panel.TFrame")
        row_h.pack(fill=tk.X, pady=2)
        ttk.Label(row_h, text="Height (in):", width=10, style="Panel.TLabel").pack(side=tk.LEFT)
        self.badge_h_in_var = tk.StringVar(value="2")
        ttk.Entry(row_h, textvariable=self.badge_h_in_var, width=8).pack(side=tk.LEFT)

        row_dpi = ttk.Frame(size_frame, style="Panel.TFrame")
        row_dpi.pack(fill=tk.X, pady=2)
        ttk.Label(row_dpi, text="DPI:", width=10, style="Panel.TLabel").pack(side=tk.LEFT)
        self.badge_dpi_var = tk.StringVar(value="300")
        ttk.Entry(row_dpi, textvariable=self.badge_dpi_var, width=8).pack(side=tk.LEFT)

        self.badge_size_label = ttk.Label(size_frame, text="1050 x 600 px", style="Panel.TLabel")
        self.badge_size_label.pack(anchor=tk.W, pady=(4, 2))

        ttk.Button(size_frame, text="Apply Badge Size",
                   command=self._apply_badge_size).pack(fill=tk.X, pady=(4, 0))

        # --- PDF Layout Section ---
        pdf_frame = ttk.LabelFrame(inner, text="PDF Layout", padding=(8, 6))
        pdf_frame.pack(fill=tk.X, **pad)

        row_cols = ttk.Frame(pdf_frame, style="Panel.TFrame")
        row_cols.pack(fill=tk.X, pady=2)
        ttk.Label(row_cols, text="Columns:", width=10, style="Panel.TLabel").pack(side=tk.LEFT)
        self.pdf_cols_var = tk.StringVar(value=str(self.config.badges_per_row))
        ttk.Entry(row_cols, textvariable=self.pdf_cols_var, width=6).pack(side=tk.LEFT)

        row_rows = ttk.Frame(pdf_frame, style="Panel.TFrame")
        row_rows.pack(fill=tk.X, pady=2)
        ttk.Label(row_rows, text="Rows:", width=10, style="Panel.TLabel").pack(side=tk.LEFT)
        self.pdf_rows_var = tk.StringVar(value=str(self.config.badges_per_col))
        ttk.Entry(row_rows, textvariable=self.pdf_rows_var, width=6).pack(side=tk.LEFT)

        row_page = ttk.Frame(pdf_frame, style="Panel.TFrame")
        row_page.pack(fill=tk.X, pady=2)
        ttk.Label(row_page, text="Page:", width=10, style="Panel.TLabel").pack(side=tk.LEFT)
        self.pdf_page_var = tk.StringVar(value=self.config.page_size)
        ttk.Combobox(row_page, textvariable=self.pdf_page_var,
                      values=["letter", "A4"], state="readonly", width=8).pack(side=tk.LEFT)

        row_margin = ttk.Frame(pdf_frame, style="Panel.TFrame")
        row_margin.pack(fill=tk.X, pady=2)
        ttk.Label(row_margin, text="Margin (mm):", width=12, style="Panel.TLabel").pack(side=tk.LEFT)
        self.pdf_margin_var = tk.StringVar(value=str(self.config.margin_mm))
        ttk.Entry(row_margin, textvariable=self.pdf_margin_var, width=6).pack(side=tk.LEFT)

        row_spacing = ttk.Frame(pdf_frame, style="Panel.TFrame")
        row_spacing.pack(fill=tk.X, pady=2)
        ttk.Label(row_spacing, text="Spacing (mm):", width=12, style="Panel.TLabel").pack(side=tk.LEFT)
        self.pdf_spacing_var = tk.StringVar(value=str(self.config.spacing_mm))
        ttk.Entry(row_spacing, textvariable=self.pdf_spacing_var, width=6).pack(side=tk.LEFT)

        ttk.Button(pdf_frame, text="Apply PDF Settings",
                   command=self._apply_pdf_settings).pack(fill=tk.X, pady=(4, 0))

    def _lookup_panel_bg(self) -> str:
        """Return the ttk Panel.TFrame background color for the embedded Canvas."""
        try:
            style = ttk.Style()
            bg = style.lookup("Panel.TFrame", "background")
            return bg or "SystemButtonFace"
        except Exception:
            return "SystemButtonFace"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_side(self, side: str):
        """Switch which side's fields are shown."""
        self._current_side = side
        self._selected_idx = -1
        self.refresh_field_list()

    def refresh_columns(self):
        """Update the column dropdown from CSV headers."""
        self.column_combo["values"] = self.csv_data.headers
        if self.csv_data.headers:
            self.column_var.set(self.csv_data.headers[0])
        # Keep any open rule rows in sync with the new header list, but
        # preserve any column already chosen (even if no longer present).
        for entry in self._rule_rows:
            current = entry["column_var"].get()
            headers = list(self.csv_data.headers)
            if current and current not in headers:
                headers.append(current)
            entry["combo"]["values"] = headers

    def refresh_field_list(self):
        """Update the placed fields listbox (filtered by current side)."""
        self.field_listbox.delete(0, tk.END)
        self._listbox_to_field_idx = []
        for idx, fp in enumerate(self.config.fields):
            if fp.side != self._current_side:
                continue
            if fp.static_text:
                label = f'"{fp.static_text}"'
            elif fp.rules:
                label = f"{fp.csv_column or 'conditional'} (conditional)"
            else:
                label = fp.csv_column
            self.field_listbox.insert(tk.END, label)
            self._listbox_to_field_idx.append(idx)
        # Restore selection if still valid
        if self._selected_idx in self._listbox_to_field_idx:
            lb_idx = self._listbox_to_field_idx.index(self._selected_idx)
            self.field_listbox.selection_set(lb_idx)

    def refresh_fonts(self):
        """Load available font families into the font dropdown."""
        self._font_families = get_font_families()
        self.font_combo["values"] = self._font_families
        if self._font_families:
            self.font_var.set(self._font_families[0])

    def select_field(self, idx: int):
        """Select a field by global index and populate the property editors."""
        self._selected_idx = idx
        self.field_listbox.selection_clear(0, tk.END)
        if 0 <= idx < len(self.config.fields):
            # Map global index to listbox index
            if idx in self._listbox_to_field_idx:
                lb_idx = self._listbox_to_field_idx.index(idx)
                self.field_listbox.selection_set(lb_idx)
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
        self.static_text_var.set(fp.static_text)
        self.x_var.set(str(round(fp.x, 1)))
        self.y_var.set(str(round(fp.y, 1)))
        self.font_var.set(fp.font_family)
        self.size_var.set(str(fp.font_size))
        self.maxw_var.set(str(fp.max_width))
        self.wrap_var.set(fp.wrap)
        self.line_height_var.set(str(fp.line_height))
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
        self._render_rules(fp.rules)
        self._updating = False

    def _render_rules(self, rules: List[ConditionalRule]):
        """Rebuild rule rows in the properties panel from a rules list."""
        for row in self._rule_rows:
            row["frame"].destroy()
        self._rule_rows = []
        for rule in rules:
            self._append_rule_row(rule.column, rule.text,
                                  getattr(rule, "match", "y") or "y")

    def _append_rule_row(self, column: str = "", text: str = "", match: str = "y"):
        """Add a single rule row to the rules frame."""
        row = ttk.Frame(self.rules_frame, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=1)

        column_var = tk.StringVar(value=column)
        headers = list(self.csv_data.headers)
        if column and column not in headers:
            headers = headers + [column]
        col_combo = ttk.Combobox(row, textvariable=column_var, values=headers,
                                  state="readonly", width=10)
        col_combo.pack(side=tk.LEFT, padx=(0, 2))

        # Match mode: "y" = starts with Y; "non_dash" = any non-blank/non-dash value.
        match_labels = {"y": "Y prefix", "non_dash": "not -/blank"}
        match_var = tk.StringVar(value=match_labels.get(match, "Y prefix"))
        match_combo = ttk.Combobox(row, textvariable=match_var,
                                    values=list(match_labels.values()),
                                    state="readonly", width=11)
        match_combo.pack(side=tk.LEFT, padx=(0, 2))

        text_var = tk.StringVar(value=text)
        text_entry = ttk.Entry(row, textvariable=text_var, width=10)
        text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        entry = {"frame": row, "column_var": column_var, "text_var": text_var,
                 "combo": col_combo, "match_var": match_var,
                 "match_labels": match_labels}

        def remove():
            row.destroy()
            if entry in self._rule_rows:
                self._rule_rows.remove(entry)

        tk.Button(row, text="×", width=2, padx=0, pady=0,
                  font=("Segoe UI", 9), relief="flat", bg="#e0e0e0",
                  activebackground="#c8c8c8", command=remove).pack(side=tk.LEFT)

        self._rule_rows.append(entry)

    def _add_rule_row(self):
        """Add an empty rule row (only if a field is selected)."""
        if self._selected_idx < 0:
            return
        self._append_rule_row()

    def _read_rules(self) -> List[ConditionalRule]:
        """Collect ConditionalRule objects from the current UI rows."""
        rules = []
        for entry in self._rule_rows:
            column = entry["column_var"].get()
            text = entry["text_var"].get()
            label = entry["match_var"].get()
            labels = entry["match_labels"]
            # Reverse-map the display label to the stored key
            match = next((k for k, v in labels.items() if v == label), "y")
            if column or text:
                rules.append(ConditionalRule(column=column, text=text, match=match))
        return rules

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
            side=self._current_side,
        )
        self.config.fields.append(fp)
        self.refresh_field_list()
        idx = len(self.config.fields) - 1
        self.select_field(idx)
        if self.on_field_added:
            self.on_field_added(fp)

    def _add_static_text(self):
        """Create a static-text field at badge center with default placeholder text."""
        fp = FieldPlacement(
            csv_column="",
            static_text="Text",
            x=self.config.badge_width / 2,
            y=self.config.badge_height / 2,
            font_family=self.font_var.get() or "Arial",
            font_size=24,
            side=self._current_side,
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
        fp.wrap = self.wrap_var.get()
        try:
            fp.line_height = float(self.line_height_var.get())
        except ValueError:
            pass
        fp.font_color = self.color_var.get() or fp.font_color
        fp.bold = self.bold_var.get()
        fp.italic = self.italic_var.get()
        fp.alignment = self.align_var.get()
        fp.static_text = self.static_text_var.get()
        fp.rules = self._read_rules()

        if self.on_field_updated:
            self.on_field_updated(idx)

    def _apply_pdf_settings(self):
        """Read PDF layout inputs and write them into config."""
        try:
            cols = max(1, int(self.pdf_cols_var.get()))
        except ValueError:
            cols = self.config.badges_per_row
        try:
            rows = max(1, int(self.pdf_rows_var.get()))
        except ValueError:
            rows = self.config.badges_per_col
        try:
            margin = max(0.0, float(self.pdf_margin_var.get()))
        except ValueError:
            margin = self.config.margin_mm
        try:
            spacing = max(0.0, float(self.pdf_spacing_var.get()))
        except ValueError:
            spacing = self.config.spacing_mm

        self.config.badges_per_row = cols
        self.config.badges_per_col = rows
        self.config.page_size = self.pdf_page_var.get() or "letter"
        self.config.margin_mm = margin
        self.config.spacing_mm = spacing

    def _apply_badge_size(self):
        """Compute pixel dimensions from inches + DPI and update config."""
        try:
            w_in = float(self.badge_w_in_var.get())
            h_in = float(self.badge_h_in_var.get())
            dpi = int(self.badge_dpi_var.get())
        except ValueError:
            return

        new_w = max(1, round(w_in * dpi))
        new_h = max(1, round(h_in * dpi))
        self.config.badge_width = new_w
        self.config.badge_height = new_h
        self.badge_size_label.config(text=f'{new_w} x {new_h} px ({w_in}" x {h_in}" @ {dpi} DPI)')
        if self.on_badge_size_changed:
            self.on_badge_size_changed(new_w, new_h)

    def update_badge_size_display(self):
        """Update the badge size controls to reflect current config."""
        dpi = self.config.dpi or 300
        w_in = round(self.config.badge_width / dpi, 2)
        h_in = round(self.config.badge_height / dpi, 2)
        self.badge_w_in_var.set(str(w_in))
        self.badge_h_in_var.set(str(h_in))
        self.badge_dpi_var.set(str(dpi))
        self.badge_size_label.config(
            text=f'{self.config.badge_width} x {self.config.badge_height} px ({w_in}" x {h_in}" @ {dpi} DPI)'
        )

    def update_pdf_settings_display(self):
        """Update the PDF Layout inputs to reflect current config."""
        self.pdf_cols_var.set(str(self.config.badges_per_row))
        self.pdf_rows_var.set(str(self.config.badges_per_col))
        self.pdf_page_var.set(self.config.page_size)
        self.pdf_margin_var.set(str(self.config.margin_mm))
        self.pdf_spacing_var.set(str(self.config.spacing_mm))

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
            lb_idx = sel[0]
            if lb_idx < len(self._listbox_to_field_idx):
                idx = self._listbox_to_field_idx[lb_idx]
                self._selected_idx = idx
                self._load_field_properties(self.config.fields[idx])
                if self.on_field_selected:
                    self.on_field_selected(idx)
