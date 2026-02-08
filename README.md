# Badge Designer

A convention badge designer with two interfaces: a **desktop app** (Tkinter) and a **web app** (Flask). Design badge templates with custom text fields, load attendee data from CSV, preview badges in real time, and export to PDF for printing.

## Features

- **Visual badge editor** - drag-and-drop text fields onto a background image
- **CSV data binding** - load attendee data and preview each badge individually
- **Custom styling** - font family, size, color, bold/italic, alignment per field
- **PDF export** - batch export all badges in a configurable grid layout
- **Template system** - save/load badge designs as reusable JSON templates
- **Manual entry** - add badges by hand with auto-incrementing badge numbers
- **Search** - find specific badges across all CSV fields
- **Single badge export** - download individual badges as PNG or PDF

## Getting Started

### Requirements

- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

### Desktop App

```
python badge_app.py
```

Or double-click `Badge Designer.bat` on Windows.

### Web App (Local)

```
python -m flask --app web.app run --host 0.0.0.0 --port 5000
```

Or double-click `Web Badge Designer.bat` on Windows. Open http://localhost:5000 in your browser.

### Deploy to Render

1. Push this repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect the repo — Render auto-detects settings from `render.yaml`
4. Deploy

## Usage

1. **Open a background image** (PNG, JPG, etc.) to set the badge dimensions
2. **Open a CSV file** with attendee data (name, badge number, etc.)
3. **Add fields** by selecting a CSV column and clicking Add
4. **Position fields** by dragging them on the canvas or editing X/Y in the properties panel
5. **Style fields** with font, size, color, bold, italic, and alignment
6. **Navigate rows** to preview each badge with real data
7. **Export PDF** to generate a print-ready file with all badges

## Project Structure

```
badge_app.py                # Desktop entry point
models/
  badge_config.py           # BadgeConfig + FieldPlacement dataclasses
  csv_data.py               # CSV loader
export/
  badge_renderer.py         # Renders badges with Pillow
  pdf_export.py             # PDF generation with ReportLab
utils/
  fonts.py                  # System font discovery (Windows + Linux)
  image_utils.py            # Coordinate conversion helpers
gui/
  main_window.py            # Tkinter main window
  canvas_editor.py          # Desktop canvas with drag-drop
  field_panel.py            # Desktop field properties panel
  dialogs.py                # Desktop modal dialogs
web/
  app.py                    # Flask API routes
  state.py                  # In-memory session state
  templates/index.html      # Web UI
  static/css/style.css      # Stylesheet
  static/js/                # JS modules (editor, fields, nav, dialogs)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop GUI | Python + Tkinter |
| Web frontend | Vanilla JS + SVG |
| Web backend | Flask |
| Image rendering | Pillow |
| PDF generation | ReportLab |
| Production server | Gunicorn |
