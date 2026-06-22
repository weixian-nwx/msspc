"""Central paths and constants for the attendance program.

All working data lives in a single ``data/`` folder next to the project root so
the program never depends on where the user's original files were located.
"""
from __future__ import annotations

import os
from datetime import datetime

# Project root = parent of this file's directory (app/).
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")

# Persistent state.
DB_PATH = os.path.join(DATA_DIR, "app.db")

# Copies of the user's uploads (kept so we are crash-safe and self-contained).
EXPECTED_XLSX = os.path.join(DATA_DIR, "expected_participants.xlsx")
TEMPLATE_PPTX = os.path.join(DATA_DIR, "template_deck.pptx")

# Regenerated attendance export (overwritten on every scan).
ATTENDANCE_XLSX = os.path.join(DATA_DIR, "attendance.xlsx")

# Required columns in the expected-participants excel (matched case/space-insensitively).
COL_QR_ID = "unique qr id"
COL_NAME = "name"
COL_TITLE = "title"
COL_GRADE = "grade"
REQUIRED_COLUMNS = [COL_QR_ID, COL_NAME, COL_TITLE, COL_GRADE]

# Roles and slide kinds used in the slide-mapping model.
ROLE_PRESENT = "present"
ROLE_ABSENT = "absent"
ROLES = [ROLE_PRESENT, ROLE_ABSENT]

KIND_TITLE = "title"        # the section heading slide (insert-after anchor)
KIND_TEMPLATE = "template"  # the per-attendee slide cloned and filled
KINDS = [KIND_TITLE, KIND_TEMPLATE]

# Seconds the same QR string is ignored after a successful decode (debounce).
SCAN_DEBOUNCE_SECONDS = 3.0


def ensure_data_dir() -> None:
    """Create the data directory if it does not yet exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def timestamped_deck_path() -> str:
    """Path for a freshly populated deck, unique per generation."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(DATA_DIR, f"attendance_deck_{stamp}.pptx")
