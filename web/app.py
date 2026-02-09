"""Flask application for the Web Badge Designer."""

import sys
import os
import json
import uuid
import tempfile
import threading
from io import BytesIO
from typing import Optional

from urllib.parse import urlparse

from flask import (
    Flask, render_template, request, jsonify, send_file, abort
)
from PIL import Image

Image.MAX_IMAGE_PIXELS = 25_000_000

# Add parent directory so we can import shared modules
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from models.badge_config import BadgeConfig, FieldPlacement
from models.csv_data import CSVData
from export.badge_renderer import render_badge
from export.pdf_export import export_pdf
from utils.fonts import get_font_families
from web.state import state

app = Flask(__name__)
app.secret_key = os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit

ALLOWED_HOSTS = {"localhost", "127.0.0.1"}


@app.before_request
def csrf_check():
    """Reject non-GET/HEAD/OPTIONS requests with a foreign Origin or Referer."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if origin:
        host = urlparse(origin).hostname
        if host not in ALLOWED_HOSTS:
            return jsonify(error="Forbidden: cross-origin request"), 403

FIELD_ALLOWED_KEYS = {
    "x", "y", "font_family", "font_size", "font_color",
    "bold", "italic", "alignment", "max_width",
}

# Temp directory for uploads and exports
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "badge_designer_web")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

@app.route("/api/upload-image", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return jsonify(error="No file provided"), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify(error="Empty filename"), 400

    try:
        img = Image.open(f.stream)
        pixels = img.width * img.height
        if pixels > Image.MAX_IMAGE_PIXELS:
            return jsonify(error=f"Image too large ({pixels:,} pixels, max {Image.MAX_IMAGE_PIXELS:,})"), 400
        img = img.convert("RGBA")
    except Exception as e:
        return jsonify(error=f"Invalid image: {e}"), 400

    state.background = img
    state.background_filename = f.filename
    state.config.badge_width = img.width
    state.config.badge_height = img.height

    return jsonify(
        ok=True,
        filename=f.filename,
        width=img.width,
        height=img.height,
    )


@app.route("/api/background-info")
def background_info():
    return jsonify(
        has_background=state.background is not None,
        filename=state.background_filename,
    )


@app.route("/api/background-image")
def background_image():
    if state.background is None:
        abort(404)
    buf = BytesIO()
    state.background.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/upload-csv", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        return jsonify(error="No file provided"), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify(error="Empty filename"), 400

    # Save to temp then load
    tmp_path = os.path.join(UPLOAD_DIR, "uploaded.csv")
    f.save(tmp_path)
    try:
        state.csv_data.load(tmp_path)
    except Exception as e:
        return jsonify(error=f"CSV error: {e}"), 400

    state.csv_filename = f.filename
    state.current_row = 0

    return jsonify(
        ok=True,
        filename=f.filename,
        headers=state.csv_data.headers,
        row_count=state.csv_data.row_count,
    )


@app.route("/api/download-csv")
def download_csv():
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400
    tmp_path = os.path.join(UPLOAD_DIR, "download.csv")
    state.csv_data.save(tmp_path)
    return send_file(
        tmp_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=state.csv_filename or "badges.csv",
    )


@app.route("/api/csv/save", methods=["POST"])
def save_csv():
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400
    if not state.csv_data.file_path:
        return jsonify(error="No file path set"), 400
    try:
        state.csv_data.save(state.csv_data.file_path)
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/api/upload-template", methods=["POST"])
def upload_template():
    if "file" not in request.files:
        return jsonify(error="No file provided"), 400
    f = request.files["file"]
    try:
        data = json.load(f.stream)
        state.config = BadgeConfig.from_dict(data)
        return jsonify(ok=True, config=state.config.to_dict())
    except Exception as e:
        return jsonify(error=f"Invalid template: {e}"), 400


@app.route("/api/download-template")
def download_template():
    buf = BytesIO()
    buf.write(json.dumps(state.config.to_dict(), indent=2).encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name="badge_template.json",
    )


# ---------------------------------------------------------------------------
# Badge config & fields
# ---------------------------------------------------------------------------

@app.route("/api/config")
def get_config():
    return jsonify(state.config.to_dict())


@app.route("/api/config", methods=["PUT"])
def update_config():
    data = request.get_json()
    for key in ("badges_per_row", "badges_per_col", "page_size",
                "margin_mm", "spacing_mm", "badge_width", "badge_height"):
        if key in data:
            setattr(state.config, key, data[key])
    return jsonify(ok=True, config=state.config.to_dict())


@app.route("/api/fields")
def get_fields():
    return jsonify(fields=[f.to_dict() for f in state.config.fields])


@app.route("/api/fields", methods=["POST"])
def add_field():
    data = request.get_json()
    fp = FieldPlacement.from_dict(data)
    state.config.fields.append(fp)
    idx = len(state.config.fields) - 1
    return jsonify(ok=True, index=idx, field=fp.to_dict())


@app.route("/api/fields/<int:idx>", methods=["PUT"])
def update_field(idx):
    if idx < 0 or idx >= len(state.config.fields):
        return jsonify(error="Invalid field index"), 404
    data = request.get_json()
    fp = state.config.fields[idx]
    for key, val in data.items():
        if key in FIELD_ALLOWED_KEYS:
            setattr(fp, key, val)
    return jsonify(ok=True, field=fp.to_dict())


@app.route("/api/fields/<int:idx>", methods=["DELETE"])
def delete_field(idx):
    if idx < 0 or idx >= len(state.config.fields):
        return jsonify(error="Invalid field index"), 404
    state.config.fields.pop(idx)
    return jsonify(ok=True)


@app.route("/api/fonts")
def get_fonts():
    families = get_font_families()
    return jsonify(fonts=families)


# ---------------------------------------------------------------------------
# CSV data operations
# ---------------------------------------------------------------------------

@app.route("/api/csv/info")
def csv_info():
    return jsonify(
        loaded=state.csv_data.is_loaded,
        filename=state.csv_filename,
        headers=state.csv_data.headers,
        row_count=state.csv_data.row_count,
        current_row=state.current_row,
    )


@app.route("/api/csv/row/<int:idx>")
def get_row(idx):
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400
    if idx < 0 or idx >= state.csv_data.row_count:
        return jsonify(error="Row index out of range"), 404
    state.current_row = idx
    return jsonify(
        row=state.csv_data.rows[idx],
        index=idx,
        total=state.csv_data.row_count,
    )


@app.route("/api/csv/row", methods=["POST"])
def add_row():
    data = request.get_json()
    row = data.get("row", {})
    # Ensure all headers exist in the new row
    for h in state.csv_data.headers:
        if h not in row:
            row[h] = ""
    # If no headers yet, create them from keys
    if not state.csv_data.headers:
        state.csv_data.headers = list(row.keys())
    state.csv_data.rows.append(row)
    idx = len(state.csv_data.rows) - 1
    state.current_row = idx
    return jsonify(ok=True, index=idx, row=row)


@app.route("/api/csv/row/<int:idx>", methods=["PUT"])
def update_row(idx):
    if idx < 0 or idx >= state.csv_data.row_count:
        return jsonify(error="Row index out of range"), 404
    data = request.get_json()
    row = data.get("row", {})
    for key, val in row.items():
        state.csv_data.rows[idx][key] = val
    return jsonify(ok=True, row=state.csv_data.rows[idx])


@app.route("/api/csv/row/<int:idx>", methods=["DELETE"])
def delete_row(idx):
    if idx < 0 or idx >= state.csv_data.row_count:
        return jsonify(error="Row index out of range"), 404
    state.csv_data.rows.pop(idx)
    if state.current_row >= state.csv_data.row_count and state.csv_data.row_count > 0:
        state.current_row = state.csv_data.row_count - 1
    elif state.csv_data.row_count == 0:
        state.current_row = 0
    return jsonify(ok=True, row_count=state.csv_data.row_count)


@app.route("/api/csv/search")
def search_csv():
    q = request.args.get("q", "").lower().strip()
    if not q or not state.csv_data.is_loaded:
        return jsonify(results=[])
    results = []
    for i, row in enumerate(state.csv_data.rows):
        for val in row.values():
            if q in str(val).lower():
                results.append({"index": i, "row": row})
                break
    return jsonify(results=results)


@app.route("/api/csv/next-badge-number")
def next_badge_number():
    """Find the highest numeric badge number and return +1."""
    col = request.args.get("column", "Badge Number")
    max_num = 0
    for row in state.csv_data.rows:
        val = row.get(col, "")
        try:
            num = int(val)
            if num > max_num:
                max_num = num
        except (ValueError, TypeError):
            pass
    return jsonify(next=max_num + 1)


# ---------------------------------------------------------------------------
# Rendering & export
# ---------------------------------------------------------------------------

@app.route("/api/preview/<int:row_idx>")
def preview_badge(row_idx):
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400
    if row_idx < 0 or row_idx >= state.csv_data.row_count:
        return jsonify(error="Row index out of range"), 404

    img = render_badge(state.config, state.csv_data, row_idx, state.background)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/preview-custom")
def preview_custom():
    """Render a badge with manually supplied values (for manual entry preview)."""
    values_json = request.args.get("values", "{}")
    try:
        values = json.loads(values_json)
    except json.JSONDecodeError:
        return jsonify(error="Invalid JSON"), 400

    # Build a temporary CSVData with a single row
    temp_csv = CSVData()
    temp_csv.headers = list(values.keys())
    temp_csv.rows = [values]

    img = render_badge(state.config, temp_csv, 0, state.background)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/export-pdf", methods=["POST"])
def start_pdf_export():
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400

    task_id = str(uuid.uuid4())[:8]
    output_path = os.path.join(UPLOAD_DIR, f"badges_{task_id}.pdf")

    task = {
        "status": "running",
        "progress": 0,
        "total": state.csv_data.row_count,
        "path": output_path,
        "error": None,
    }
    with state.lock:
        state.export_tasks[task_id] = task

    # Capture current state for the thread
    config = BadgeConfig.from_dict(state.config.to_dict())
    csv_data_copy = CSVData()
    csv_data_copy.headers = list(state.csv_data.headers)
    csv_data_copy.rows = [dict(r) for r in state.csv_data.rows]
    bg = state.background.copy() if state.background else None

    def run_export():
        def on_progress(n):
            with state.lock:
                task["progress"] = n

        try:
            export_pdf(
                config, csv_data_copy, output_path,
                background=bg,
                on_progress=on_progress,
            )
            with state.lock:
                task["status"] = "done"
        except Exception as e:
            with state.lock:
                task["status"] = "error"
                task["error"] = str(e)

    t = threading.Thread(target=run_export, daemon=True)
    t.start()

    return jsonify(task_id=task_id)


@app.route("/api/export-pdf/status/<task_id>")
def pdf_export_status(task_id):
    with state.lock:
        task = state.export_tasks.get(task_id)
        if not task:
            return jsonify(error="Unknown task"), 404
        return jsonify(
            status=task["status"],
            progress=task["progress"],
            total=task["total"],
            error=task["error"],
        )


@app.route("/api/export-pdf/download/<task_id>")
def download_pdf(task_id):
    task = state.export_tasks.get(task_id)
    if not task or task["status"] != "done":
        return jsonify(error="PDF not ready"), 400
    return send_file(
        task["path"],
        mimetype="application/pdf",
        as_attachment=True,
        download_name="badges.pdf",
    )


@app.route("/api/export-single-pdf/<int:row_idx>")
def export_single_pdf(row_idx):
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400
    if row_idx < 0 or row_idx >= state.csv_data.row_count:
        return jsonify(error="Row index out of range"), 404

    # Create a temp CSV with just one row
    temp_csv = CSVData()
    temp_csv.headers = list(state.csv_data.headers)
    temp_csv.rows = [dict(state.csv_data.rows[row_idx])]

    output_path = os.path.join(UPLOAD_DIR, f"badge_single_{row_idx}.pdf")
    export_pdf(state.config, temp_csv, output_path, background=state.background)

    return send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"badge_{row_idx + 1}.pdf",
    )


@app.route("/api/export-single-image/<int:row_idx>")
def export_single_image(row_idx):
    if not state.csv_data.is_loaded:
        return jsonify(error="No CSV loaded"), 400
    if row_idx < 0 or row_idx >= state.csv_data.row_count:
        return jsonify(error="Row index out of range"), 404

    img = render_badge(state.config, state.csv_data, row_idx, state.background)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"badge_{row_idx + 1}.png",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"Badge Designer Web - http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=debug)
