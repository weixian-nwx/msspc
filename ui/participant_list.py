"""In-app participant roster with live check-in status.

Read-only view over the participants table. The owner calls ``refresh()`` after
any state change (upload, scan, clear) — there is no direct DB coupling back the
other way. Row check-boxes let the owner update several participants at once via
``bulk_toggle_requested``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
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

# The check-box lives in column 0; data columns follow.
_CHECK_COL = 0


class ParticipantList(QWidget):
    # Emitted when a row is double-clicked, carrying that participant's qr_id.
    # The owner decides what to do (confirm + toggle attendance); this widget
    # stays a read-only view over the DB.
    toggle_requested = Signal(str)

    # Emitted by the bulk actions with (qr_ids, make_present). The owner
    # confirms and applies the change; this widget only tracks the selection.
    bulk_toggle_requested = Signal(list, bool)

    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        # Filtered participants currently shown, aligned with table rows.
        self._rows: list = []
        # qr_ids currently ticked. Kept by id (not row) so selection survives
        # re-filtering and refresh().
        self._selected: set[str] = set()
        # Guards row-checkbox writes made by us (during refresh / select-all)
        # from being treated as user clicks.
        self._syncing = False

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

        # --- Bulk-action bar ---
        actions = QHBoxLayout()
        self.select_all = QCheckBox("Select all")
        self.select_all.setTristate(True)
        self.select_all.clicked.connect(self._on_select_all_clicked)
        actions.addWidget(self.select_all)

        self.selection_label = QLabel("")
        self.selection_label.setStyleSheet("color:#666;")
        actions.addWidget(self.selection_label)

        actions.addStretch(1)
        self.btn_mark_present = QPushButton("Mark present")
        self.btn_mark_present.clicked.connect(lambda: self._emit_bulk(True))
        actions.addWidget(self.btn_mark_present)

        self.btn_mark_absent = QPushButton("Mark absent")
        self.btn_mark_absent.clicked.connect(lambda: self._emit_bulk(False))
        actions.addWidget(self.btn_mark_absent)
        layout.addLayout(actions)

        # --- Table ---
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["", "Name", "Seat No", "Title", "BU", "Grade", "Status", "Check-in time"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        # All columns are user-resizable; seed sensible starting widths.
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        for col, width in enumerate((28, 160, 70, 150, 90, 60, 80, 140)):
            self.table.setColumnWidth(col, width)
        # Double-clicking a data cell toggles that participant's status; the
        # check-box column is reserved for selection.
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        self._update_selection_ui()

    # ------------------------------------------------------------------ events
    def _on_double_click(self, row: int, col: int) -> None:
        if col == _CHECK_COL:
            return
        if 0 <= row < len(self._rows):
            self.toggle_requested.emit(self._rows[row].qr_id)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._syncing or item.column() != _CHECK_COL:
            return
        row = item.row()
        if not (0 <= row < len(self._rows)):
            return
        qr_id = self._rows[row].qr_id
        if item.checkState() == Qt.Checked:
            self._selected.add(qr_id)
        else:
            self._selected.discard(qr_id)
        self._update_selection_ui()

    def _on_select_all_clicked(self, _checked: bool) -> None:
        # Target state: if everything visible is already ticked, clear it;
        # otherwise tick all visible rows.
        visible_ids = {p.qr_id for p in self._rows}
        all_selected = bool(visible_ids) and visible_ids <= self._selected
        target = not all_selected
        if target:
            self._selected |= visible_ids
        else:
            self._selected -= visible_ids

        self._syncing = True
        state = Qt.Checked if target else Qt.Unchecked
        for r in range(self.table.rowCount()):
            self.table.item(r, _CHECK_COL).setCheckState(state)
        self._syncing = False
        self._update_selection_ui()

    def _emit_bulk(self, make_present: bool) -> None:
        qr_ids = [p.qr_id for p in self._rows if p.qr_id in self._selected]
        if not qr_ids:
            return
        self.bulk_toggle_requested.emit(qr_ids, make_present)

    def clear_selection(self) -> None:
        """Drop the current tick set (owner calls this after a bulk apply)."""
        self._selected.clear()
        self.refresh()

    # -------------------------------------------------------------- selection
    def _update_selection_ui(self) -> None:
        visible_ids = {p.qr_id for p in self._rows}
        n = len(visible_ids & self._selected)
        self.selection_label.setText(f"{n} selected" if n else "")
        self.btn_mark_present.setEnabled(n > 0)
        self.btn_mark_absent.setEnabled(n > 0)

        self.select_all.blockSignals(True)
        if n == 0:
            self.select_all.setCheckState(Qt.Unchecked)
        elif n == len(visible_ids):
            self.select_all.setCheckState(Qt.Checked)
        else:
            self.select_all.setCheckState(Qt.PartiallyChecked)
        self.select_all.setEnabled(bool(visible_ids))
        self.select_all.blockSignals(False)

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

        self._rows = rows
        # Forget ticks for anyone no longer in the roster (e.g. after a reload).
        present_ids = {p.qr_id for p in self.db.all_participants()}
        self._selected &= present_ids

        self._syncing = True
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(
                Qt.Checked if p.qr_id in self._selected else Qt.Unchecked
            )
            self.table.setItem(r, _CHECK_COL, check)

            data = (
                QTableWidgetItem(p.name),
                QTableWidgetItem(p.seat_no),
                QTableWidgetItem(p.title),
                QTableWidgetItem(p.bu),
                QTableWidgetItem(p.grade),
                QTableWidgetItem("Present" if p.present else "Absent"),
                QTableWidgetItem(p.checkin_time or "—"),
            )
            for offset, item in enumerate(data):
                if p.present:
                    item.setBackground(PRESENT_BG)
                    item.setForeground(PRESENT_FG)
                self.table.setItem(r, _CHECK_COL + 1 + offset, item)
        self._syncing = False

        self._update_selection_ui()
