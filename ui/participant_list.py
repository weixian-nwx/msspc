"""In-app participant roster with live check-in status.

Read-only view over the participants table. The owner calls ``refresh()`` after
any state change (upload, scan, clear) — there is no direct DB coupling back the
other way.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db import Database

# Same "ok" palette used by ScanView for a checked-in banner.
PRESENT_BG = QColor("#d4edda")
PRESENT_FG = QColor("#1e7e34")

_FILTER_ALL = "All"
_FILTER_PRESENT = "Present"
_FILTER_ABSENT = "Absent"


class ParticipantList(QWidget):
    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- Filter bar ---
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        bar.addWidget(self.search, 1)

        bar.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems([_FILTER_ALL, _FILTER_PRESENT, _FILTER_ABSENT])
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        bar.addWidget(self.status_filter)
        layout.addLayout(bar)

        # --- Table ---
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Check-in time"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.table)

    # ------------------------------------------------------------------ refresh
    def _apply_filter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the table from the DB, honouring the search + status filter."""
        needle = self.search.text().strip().lower()
        status = self.status_filter.currentText()

        rows = []
        for p in self.db.all_participants():  # ordered by row_index (Excel order)
            if needle and needle not in p.name.lower():
                continue
            if status == _FILTER_PRESENT and not p.present:
                continue
            if status == _FILTER_ABSENT and p.present:
                continue
            rows.append(p)

        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            name_item = QTableWidgetItem(p.name)
            status_item = QTableWidgetItem("Present" if p.present else "Absent")
            time_item = QTableWidgetItem(p.checkin_time or "—")
            for c, item in enumerate((name_item, status_item, time_item)):
                if p.present:
                    item.setBackground(PRESENT_BG)
                    item.setForeground(PRESENT_FG)
                self.table.setItem(r, c, item)
