"""Convention Badge Designer - Entry Point."""

import sys
import os
import tkinter as tk
from tkinter import ttk

# Ensure the app directory is on the import path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from gui.main_window import MainWindow

# Colors used throughout the app
COLORS = {
    "bg": "#f0f0f0",
    "toolbar_bg": "#e2e2e2",
    "accent": "#0078D4",
    "accent_hover": "#1a86d9",
    "accent_fg": "#ffffff",
    "status_bg": "#e0e0e0",
    "canvas_bg": "#d6d6d6",
    "panel_bg": "#f5f5f5",
    "border": "#c0c0c0",
    "text": "#1a1a1a",
    "text_secondary": "#555555",
}


def configure_styles():
    """Set up ttk theme and custom styles for a modern look."""
    style = ttk.Style()
    style.theme_use("clam")

    # General
    style.configure(".", font=("Segoe UI", 9), background=COLORS["bg"],
                    foreground=COLORS["text"])

    # Frames
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Toolbar.TFrame", background=COLORS["toolbar_bg"])
    style.configure("Panel.TFrame", background=COLORS["panel_bg"])
    style.configure("Status.TFrame", background=COLORS["status_bg"])

    # Labels
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Toolbar.TLabel", background=COLORS["toolbar_bg"])
    style.configure("Status.TLabel", background=COLORS["status_bg"],
                    foreground=COLORS["text_secondary"], font=("Segoe UI", 8))
    style.configure("Header.TLabel", font=("Segoe UI", 9, "bold"))
    style.configure("Panel.TLabel", background=COLORS["panel_bg"])

    # Buttons - modern flat style
    style.configure("TButton", padding=(8, 4), font=("Segoe UI", 9))
    style.map("TButton",
              background=[("active", "#d0d0d0"), ("!active", COLORS["bg"])],
              relief=[("pressed", "sunken"), ("!pressed", "flat")])

    # Accent button (for primary actions)
    style.configure("Accent.TButton", background=COLORS["accent"],
                    foreground=COLORS["accent_fg"], padding=(10, 5),
                    font=("Segoe UI", 9, "bold"))
    style.map("Accent.TButton",
              background=[("active", COLORS["accent_hover"]),
                          ("!active", COLORS["accent"])],
              foreground=[("active", COLORS["accent_fg"]),
                          ("!active", COLORS["accent_fg"])])

    # Toolbar buttons
    style.configure("Toolbar.TButton", padding=(6, 3), font=("Segoe UI", 8),
                    background=COLORS["toolbar_bg"])
    style.map("Toolbar.TButton",
              background=[("active", "#c8c8c8"), ("!active", COLORS["toolbar_bg"])],
              relief=[("pressed", "sunken"), ("!pressed", "flat")])

    # LabelFrame
    style.configure("TLabelframe", background=COLORS["panel_bg"],
                    foreground=COLORS["text"])
    style.configure("TLabelframe.Label", background=COLORS["panel_bg"],
                    foreground=COLORS["accent"], font=("Segoe UI", 9, "bold"))

    # Entry
    style.configure("TEntry", padding=3)

    # Combobox
    style.configure("TCombobox", padding=3)

    # Checkbutton
    style.configure("TCheckbutton", background=COLORS["panel_bg"])

    # Radiobutton
    style.configure("TRadiobutton", background=COLORS["panel_bg"])

    # Separator
    style.configure("TSeparator", background=COLORS["border"])

    # Progressbar
    style.configure("TProgressbar", troughcolor=COLORS["bg"],
                    background=COLORS["accent"])


def main():
    root = tk.Tk()
    root.configure(bg=COLORS["bg"])
    configure_styles()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
