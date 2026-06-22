"""Entry point for the attendance taking program."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app import config
from app.db import Database
from ui.main_window import MainWindow


def main() -> int:
    config.ensure_data_dir()

    app = QApplication(sys.argv)
    app.setApplicationName("Attendance Taking")

    db = Database(config.DB_PATH)
    db.init_schema()

    window = MainWindow(db)
    window.show()

    exit_code = app.exec()
    db.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
