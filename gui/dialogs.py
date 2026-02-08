"""File pickers, export progress dialog, manual entry dialog, and print dialog."""

import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from typing import Callable, Dict, List, Optional

from PIL import Image, ImageTk


class ExportProgressDialog(tk.Toplevel):
    """Modal dialog showing PDF export progress with a progress bar."""

    def __init__(self, parent, total: int, export_func: Callable, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("Exporting PDF...")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.total = total
        self.export_func = export_func
        self._cancelled = False
        self._error: Optional[str] = None

        # Center on parent
        self.geometry("360x130")
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 360) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 130) // 2
        self.geometry(f"+{px}+{py}")

        self._build_ui()
        self._start_export()

    def _build_ui(self):
        self.configure(bg="#f0f0f0")
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        ttk.Label(frame, text="Generating badges...", font=("Segoe UI", 10)).pack(pady=(0, 8))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            frame, variable=self.progress_var, maximum=self.total, length=300
        )
        self.progress_bar.pack(fill=tk.X, pady=4)

        self.status_label = ttk.Label(frame, text=f"0 / {self.total}", font=("Segoe UI", 9))
        self.status_label.pack(pady=4)

        self.btn_cancel = ttk.Button(frame, text="Cancel", command=self._cancel)
        self.btn_cancel.pack(pady=(4, 0))

    def _start_export(self):
        """Run the export in a background thread."""
        self._thread = threading.Thread(target=self._run_export, daemon=True)
        self._thread.start()

    def _run_export(self):
        try:
            self.export_func(self._on_progress, self._is_cancelled)
        except Exception as e:
            self._error = str(e)
        finally:
            self.after(0, self._finish)

    def _on_progress(self, current: int):
        """Called from the export thread to update progress."""
        self.after(0, self._update_ui, current)

    def _update_ui(self, current: int):
        self.progress_var.set(current)
        self.status_label.config(text=f"{current} / {self.total}")

    def _is_cancelled(self) -> bool:
        return self._cancelled

    def _cancel(self):
        self._cancelled = True
        self.btn_cancel.config(state="disabled")
        self.btn_cancel.config(text="Cancelling...")

    def _finish(self):
        if self._error:
            messagebox.showerror("Export Error", self._error, parent=self)
        self.grab_release()
        self.destroy()


class ManualEntryDialog(tk.Toplevel):
    """Dialog for typing in field values to create a single badge."""

    def __init__(self, parent, columns: List[str],
                 on_preview: Callable[[Dict[str, str]], None],
                 on_accept: Callable[[Dict[str, str]], None],
                 on_export_pdf: Callable[[Dict[str, str]], None],
                 on_save_image: Callable[[Dict[str, str]], None],
                 on_close: Callable[[], None],
                 defaults: Optional[Dict[str, str]] = None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self.title("Manual Badge Entry")
        self.resizable(False, True)
        self.transient(parent)

        self._columns = columns
        self._defaults = defaults or {}
        self._on_preview = on_preview
        self._on_accept = on_accept
        self._on_export_pdf = on_export_pdf
        self._on_save_image = on_save_image
        self._on_close = on_close
        self._entries: Dict[str, tk.StringVar] = {}

        self.geometry("380x%d" % min(650, 280 + 32 * len(columns)))
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() - 400
        py = parent.winfo_rooty() + 60
        self.geometry(f"+{px}+{py}")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        self.configure(bg="#f0f0f0")

        # Scrollable field entries
        top = ttk.Frame(self)
        top.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 4))

        canvas = tk.Canvas(top, highlightthickness=0, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=canvas.yview)
        self._inner = ttk.Frame(canvas)

        self._inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for col in self._columns:
            row = ttk.Frame(self._inner)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=col + ":", width=14, anchor=tk.W,
                      font=("Segoe UI", 9)).pack(side=tk.LEFT)
            var = tk.StringVar(value=self._defaults.get(col, ""))
            entry = ttk.Entry(row, textvariable=var, width=28)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._entries[col] = var

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=(4, 10))

        ttk.Button(btn_frame, text="Preview", command=self._preview).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Accept", style="Accent.TButton",
                   command=self._accept).pack(fill=tk.X, pady=2)
        ttk.Separator(btn_frame).pack(fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="Export PDF", command=self._export_pdf).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Save Image", command=self._save_image).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(fill=tk.X, pady=2)

    def get_values(self) -> Dict[str, str]:
        return {col: var.get() for col, var in self._entries.items()}

    def _preview(self):
        self._on_preview(self.get_values())

    def _accept(self):
        self._on_accept(self.get_values())
        self.destroy()

    def _export_pdf(self):
        self._on_export_pdf(self.get_values())

    def _save_image(self):
        self._on_save_image(self.get_values())

    def _clear(self):
        for var in self._entries.values():
            var.set("")
        self._on_preview(self.get_values())

    def _close(self):
        self._on_close()
        self.destroy()


def _get_printers() -> List[str]:
    """Return list of available printer names via PowerShell."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Printer | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        names = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return sorted(names)
    except Exception:
        return []


def _get_default_printer() -> str:
    """Return the default printer name via PowerShell."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-WmiObject -Query 'SELECT Name FROM Win32_Printer WHERE Default=True').Name"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        name = result.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return ""


class PrintDialog(tk.Toplevel):
    """Print dialog with printer selection, copies, and badge preview."""

    def __init__(self, parent, badge_image: Image.Image, pdf_path: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("Print Badge")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._badge_image = badge_image
        self._pdf_path = pdf_path
        self.printed = False

        self.geometry("440x420")
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 440) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 420) // 2
        self.geometry(f"+{px}+{py}")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Load printers in background so the dialog appears instantly
        self.after(50, self._load_printers)

    def _build_ui(self):
        self.configure(bg="#f0f0f0")
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Badge preview
        preview_frame = ttk.LabelFrame(outer, text="Preview", padding=(8, 6))
        preview_frame.pack(fill=tk.X, pady=(0, 6))

        max_w, max_h = 400, 180
        img = self._badge_image.copy()
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(img)
        ttk.Label(preview_frame, image=self._preview_photo).pack()

        # Printer selection
        printer_frame = ttk.LabelFrame(outer, text="Printer", padding=(8, 6))
        printer_frame.pack(fill=tk.X, pady=6)

        self.printer_var = tk.StringVar(value="Loading printers...")
        self.printer_combo = ttk.Combobox(
            printer_frame, textvariable=self.printer_var, state="readonly", width=45
        )
        self.printer_combo.pack(fill=tk.X, pady=(0, 6))

        copies_frame = ttk.Frame(printer_frame)
        copies_frame.pack(fill=tk.X)
        ttk.Label(copies_frame, text="Copies:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.copies_var = tk.IntVar(value=1)
        self.copies_spin = ttk.Spinbox(
            copies_frame, from_=1, to=99, textvariable=self.copies_var, width=5
        )
        self.copies_spin.pack(side=tk.LEFT, padx=6)

        # Buttons
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        self.btn_print = ttk.Button(
            btn_frame, text="Print", style="Accent.TButton",
            width=14, command=self._print, state=tk.DISABLED
        )
        self.btn_print.pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Button(btn_frame, text="Cancel", width=14,
                   command=self._cancel).pack(side=tk.RIGHT, padx=4)

    def _load_printers(self):
        """Populate the printer dropdown."""
        printers = _get_printers()
        default = _get_default_printer()

        if printers:
            self.printer_combo["values"] = printers
            if default and default in printers:
                self.printer_var.set(default)
            else:
                self.printer_var.set(printers[0])
            self.btn_print.config(state=tk.NORMAL)
        else:
            self.printer_var.set("No printers found")

    def _print(self):
        """Send the PDF to the selected printer."""
        printer = self.printer_var.get()
        copies = self.copies_var.get()

        if not printer or printer == "No printers found":
            messagebox.showwarning("No Printer", "Please select a printer.", parent=self)
            return

        try:
            for _ in range(copies):
                subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        f'Start-Process -FilePath "{self._pdf_path}" '
                        f'-Verb PrintTo -ArgumentList "{printer}"'
                    ],
                    capture_output=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            self.printed = True
            self.grab_release()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Print Error", f"Could not print:\n{e}", parent=self)

    def _cancel(self):
        self.grab_release()
        self.destroy()
