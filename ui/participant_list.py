"""In-app participant roster with live check-in status.

Read-only view over the participants table. The owner calls ``refresh()`` after
any state change (upload, scan, clear) — there is no direct DB coupling back the
other way.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
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

# Light green marking a checked-in ("present") row.
PRESENT_BG = QColor("#d4edda")
PRESENT_FG = QColor("#1e7e34")

_FILTER_ALL = "All"
_FILTER_PRESENT = "Present"
_FILTER_ABSENT = "Absent"


class ParticipantList(QWidget):
    # Emitted when a row is double-clicked, carrying that participant's qr_id.
    # The owner decides what to do (confirm + toggle attendance); this widget
    # stays a read-only view over the DB.
    toggle_requested = Signal(str)

    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        # Filtered participants currently shown, aligned with table rows.
        self._rows: list = []

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
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Seat No", "Title", "BU", "Grade", "Status", "Check-in time"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        # All columns are user-resizable; seed sensible starting widths.
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        for col, width in enumerate((160, 70, 150, 90, 60, 80, 140)):
            self.table.setColumnWidth(col, width)
        # Double-clicking anywhere on a row toggles that participant's status.
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

    # ------------------------------------------------------------------ refresh
    def _on_double_click(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._rows):
            self.toggle_requested.emit(self._rows[row].qr_id)

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

        self._rows = rows
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            items = (
                QTableWidgetItem(p.name),
                QTableWidgetItem(p.seat_no),
                QTableWidgetItem(p.title),
                QTableWidgetItem(p.bu),
                QTableWidgetItem(p.grade),
                QTableWidgetItem("Present" if p.present else "Absent"),
                QTableWidgetItem(p.checkin_time or "—"),
            )
            for c, item in enumerate(items):
                if p.present:
                    item.setBackground(PRESENT_BG)
                    item.setForeground(PRESENT_FG)
                self.table.setItem(r, c, item)
