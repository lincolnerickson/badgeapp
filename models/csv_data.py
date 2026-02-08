"""CSV loading and column extraction."""

import csv
from typing import List, Dict, Optional


class CSVData:
    """Loads a CSV file and exposes headers and rows."""

    def __init__(self):
        self.headers: List[str] = []
        self.rows: List[Dict[str, str]] = []
        self.file_path: str = ""

    def load(self, path: str) -> None:
        """Load CSV with utf-8-sig (handles BOM), fallback to latin-1."""
        self.file_path = path
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                with open(path, "r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    self.headers = list(reader.fieldnames or [])
                    self.rows = list(reader)
                return
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not read CSV file: {path}")

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def get_value(self, row_index: int, column: str) -> str:
        """Get a cell value, returning empty string for missing data."""
        if 0 <= row_index < len(self.rows):
            return self.rows[row_index].get(column, "")
        return ""

    def save(self, path: str) -> None:
        """Write current headers and rows to a CSV file."""
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
            writer.writerows(self.rows)
        self.file_path = path

    @property
    def is_loaded(self) -> bool:
        return len(self.headers) > 0
