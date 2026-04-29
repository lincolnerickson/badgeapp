"""In-memory application state singleton for the web badge designer."""

import sys
import os
import threading
from typing import Optional
from PIL import Image

# Add parent directory so we can import shared modules
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from models.badge_config import BadgeConfig
from models.csv_data import CSVData


class AppState:
    """Holds all session state: config, CSV data, background image."""

    def __init__(self):
        self.config: BadgeConfig = BadgeConfig()
        self.csv_data: CSVData = CSVData()
        self.background: Optional[Image.Image] = None
        self.background_filename: str = ""
        self.csv_filename: str = ""
        self.current_row: int = 0
        # PDF export tasks: {task_id: {"status": str, "progress": int, "total": int, "path": str}}
        self.export_tasks: dict = {}
        self.lock = threading.Lock()

    def reset_config(self):
        self.config = BadgeConfig()
        self.background = None
        self.background_filename = ""

    def reset_csv(self):
        self.csv_data = CSVData()
        self.csv_filename = ""
        self.current_row = 0


# Module-level singleton
state = AppState()
