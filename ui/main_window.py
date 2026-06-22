"""Main application window: uploads, mapping, scanning, populate, and clears."""
from __future__ import annotations

import os
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.db import Database
from app.excel_io import ExcelError, export_attendance, import_participants
from app.pptx_builder import BuildError, build_deck
from ui.mapping_dialog import MappingDialog
from ui.participant_list import ParticipantList
from ui.scan_view import ScanView


class MainWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Attendance Taking")
        self.resize(1040, 760)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # Left control panel.
        root.addWidget(self._build_left_panel(), 0)

        # Right: live scan view on top, participant roster below — a vertical
        # splitter lets staff trade camera size against list size during an event.
        self.scan_view = ScanView(self._handle_decode)
        scan_box = QGroupBox("Scanning")
        scan_layout = QVBoxLayout(scan_box)
        scan_layout.addWidget(self.scan_view)

        self.participant_list = ParticipantList(self.db)
        list_box = QGroupBox("Participants")
        list_layout = QVBoxLayout(list_box)
        list_layout.addWidget(self.participant_list)

        right = QSplitter(Qt.Vertical)
        right.addWidget(scan_box)
        right.addWidget(list_box)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        root.addWidget(right, 1)

        self._apply_style()
        self._refresh_state()

    # ----------------------------------------------------------- UI build
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(380)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        header = QLabel("Attendance Taking")
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        layout.addWidget(header)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#444; font-size:13px;")
        layout.addWidget(self.status_label)

        layout.addWidget(self._hline())

        # --- Step 1: data sources ---
        layout.addWidget(self._section_label("1 · Data sources"))
        self.btn_upload_excel = QPushButton("Upload expected participants (Excel)…")
        self.btn_upload_excel.clicked.connect(self._on_upload_excel)
        layout.addWidget(self.btn_upload_excel)

        self.btn_upload_template = QPushButton("Upload template deck (.pptx)…")
        self.btn_upload_template.clicked.connect(self._on_upload_template)
        layout.addWidget(self.btn_upload_template)

        self.btn_mappings = QPushButton("Configure slide mappings…")
        self.btn_mappings.clicked.connect(self._on_configure_mappings)
        layout.addWidget(self.btn_mappings)

        layout.addWidget(self._hline())

        # --- Step 2: attendance ---
        layout.addWidget(self._section_label("2 · Attendance"))
        self.btn_scan = QPushButton("Start scanning")
        self.btn_scan.setObjectName("primary")
        self.btn_scan.clicked.connect(self._on_toggle_scan)
        layout.addWidget(self.btn_scan)

        self.btn_open_attendance = QPushButton("Open attendance excel")
        self.btn_open_attendance.clicked.connect(self._on_open_attendance)
        layout.addWidget(self.btn_open_attendance)

        layout.addWidget(self._hline())

        # --- Step 3: deck ---
        layout.addWidget(self._section_label("3 · Slide deck"))
        self.btn_populate = QPushButton("Populate slide deck")
        self.btn_populate.setObjectName("primary")
        self.btn_populate.clicked.connect(self._on_populate)
        layout.addWidget(self.btn_populate)

        layout.addStretch(1)

        layout.addWidget(self._hline())
        layout.addWidget(self._section_label("Clear data"))
        self.btn_clear_attendance = QPushButton("Clear attendance")
        self.btn_clear_attendance.clicked.connect(self._on_clear_attendance)
        layout.addWidget(self.btn_clear_attendance)

        self.btn_clear_mappings = QPushButton("Clear slide mappings")
        self.btn_clear_mappings.clicked.connect(self._on_clear_mappings)
        layout.addWidget(self.btn_clear_mappings)

        self.btn_clear_template = QPushButton("Clear template deck")
        self.btn_clear_template.clicked.connect(self._on_clear_template)
        layout.addWidget(self.btn_clear_template)

        self.btn_clear_excel = QPushButton("Clear expected participants")
        self.btn_clear_excel.clicked.connect(self._on_clear_excel)
        layout.addWidget(self.btn_clear_excel)

        return panel

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#0b5ed7; font-weight:700; font-size:12px;")
        return lbl

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    # ------------------------------------------------------------- state
    def _has_excel(self) -> bool:
        return self.db.get_meta("expected_xlsx") is not None and bool(self.db.all_participants())

    def _has_template(self) -> bool:
        return self.db.get_meta("template_pptx") is not None

    def _refresh_state(self) -> None:
        has_excel = self._has_excel()
        has_template = self._has_template()
        mappings_ok = self.db.mappings_complete()
        scanning = self.scan_view.is_running()

        self.btn_mappings.setEnabled(has_template and has_excel)
        self.btn_scan.setEnabled(has_excel)
        self.btn_populate.setEnabled(has_template and mappings_ok)
        self.btn_open_attendance.setEnabled(os.path.exists(config.ATTENDANCE_XLSX))

        self.btn_clear_attendance.setEnabled(has_excel)
        self.btn_clear_mappings.setEnabled(len(self.db.get_mappings()) > 0)
        self.btn_clear_template.setEnabled(has_template)
        self.btn_clear_excel.setEnabled(has_excel)

        self.btn_scan.setText("Stop scanning" if scanning else "Start scanning")

        present, total = self.db.counts()
        lines = []
        if has_excel:
            lines.append(f"Participants: <b>{total}</b> &nbsp; Present: <b>{present}</b>")
        else:
            lines.append("No participant list loaded.")
        lines.append("Template: " + ("loaded ✓" if has_template else "not loaded"))
        if has_template:
            lines.append("Mappings: " + ("complete ✓" if mappings_ok else "incomplete"))
        self.status_label.setText("<br>".join(lines))

        self.participant_list.refresh()

    # ------------------------------------------------------------ uploads
    def _on_upload_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select expected-participants Excel", "", "Excel files (*.xlsx *.xlsm)"
        )
        if not path:
            return
        try:
            count = import_participants(path, self.db)
        except ExcelError as exc:
            QMessageBox.critical(self, "Could not import", str(exc))
            return
        # Generate an initial attendance export (all absent).
        try:
            export_attendance(self.db)
        except ExcelError:
            pass
        QMessageBox.information(self, "Imported", f"Loaded {count} participants.")
        self._refresh_state()

    def _on_upload_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select template deck", "", "PowerPoint files (*.pptx)"
        )
        if not path:
            return
        try:
            shutil.copyfile(path, config.TEMPLATE_PPTX)
        except OSError as exc:
            QMessageBox.critical(self, "Could not copy template", str(exc))
            return
        self.db.set_meta("template_pptx", config.TEMPLATE_PPTX)
        QMessageBox.information(
            self, "Template loaded", "Template deck loaded. Now configure slide mappings."
        )
        self._refresh_state()

    def _on_configure_mappings(self) -> None:
        template = self.db.get_meta("template_pptx")
        if not template:
            return
        dlg = MappingDialog(self.db, template, self)
        if dlg.exec() == QDialog.Accepted:
            QMessageBox.information(self, "Saved", "Slide mappings saved.")
        self._refresh_state()

    # ------------------------------------------------------------ scanning
    def _on_toggle_scan(self) -> None:
        if self.scan_view.is_running():
            self.scan_view.stop()
        else:
            self.scan_view.start()
        self._refresh_state()

    def _handle_decode(self, value: str) -> tuple[str, str]:
        """Called from ScanView for each decoded QR. Returns (level, message)."""
        qr = value.strip()
        participant = self.db.get_participant(qr)
        if participant is None:
            return "error", f"Unknown QR — '{qr}' is not in the participant list."
        if participant.present:
            return "warn", f"Already checked in: {participant.name} ({participant.title})"

        self.db.mark_present(qr)
        try:
            export_attendance(self.db)  # auto-save on every scan
        except ExcelError:
            pass
        # Refresh counts in the side panel.
        self._refresh_state()
        return "ok", f"Checked in: {participant.name} ({participant.title})"

    def _on_open_attendance(self) -> None:
        if os.path.exists(config.ATTENDANCE_XLSX):
            os.startfile(config.ATTENDANCE_XLSX)  # noqa: S606 (Windows-only, intended)

    # ------------------------------------------------------------- populate
    def _on_populate(self) -> None:
        out = config.timestamped_deck_path()
        try:
            build_deck(self.db, out)
        except BuildError as exc:
            QMessageBox.critical(self, "Could not populate deck", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surface unexpected pptx errors
            QMessageBox.critical(self, "Error populating deck", f"{exc}")
            return
        ret = QMessageBox.information(
            self,
            "Deck created",
            f"Saved:\n{out}\n\nOpen it now?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            os.startfile(out)  # noqa: S606

    # --------------------------------------------------------------- clears
    def _confirm(self, title: str, text: str) -> bool:
        return (
            QMessageBox.question(
                self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            == QMessageBox.Yes
        )

    def _on_clear_attendance(self) -> None:
        if not self._confirm(
            "Clear attendance",
            "Reset all check-ins to absent? The participant list and mappings are kept.",
        ):
            return
        self.db.clear_attendance()
        try:
            export_attendance(self.db)
        except ExcelError:
            pass
        self._refresh_state()

    def _on_clear_mappings(self) -> None:
        if not self._confirm("Clear slide mappings", "Delete all slide mappings?"):
            return
        self.db.clear_mappings()
        self._refresh_state()

    def _on_clear_template(self) -> None:
        if not self._confirm(
            "Clear template deck",
            "Remove the template deck? This also clears slide mappings.",
        ):
            return
        self.db.clear_mappings()
        self.db.delete_meta("template_pptx")
        _safe_remove(config.TEMPLATE_PPTX)
        self._refresh_state()

    def _on_clear_excel(self) -> None:
        if not self._confirm(
            "Clear expected participants",
            "Remove the participant list? This also clears attendance and slide mappings.",
        ):
            return
        self.db.clear_participants()  # drops participants + mappings
        self.db.delete_meta("expected_xlsx")
        _safe_remove(config.EXPECTED_XLSX)
        _safe_remove(config.ATTENDANCE_XLSX)
        self._refresh_state()

    # ------------------------------------------------------------- styling
    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f5f6f8; }
            QGroupBox {
                font-weight: 600; border: 1px solid #d7d9de; border-radius: 10px;
                margin-top: 10px; background: #ffffff;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QPushButton {
                background: #ffffff; border: 1px solid #c4c7ce; border-radius: 8px;
                padding: 9px 10px; font-size: 13px; text-align: left;
            }
            QPushButton:hover:enabled { border-color: #0b5ed7; }
            QPushButton:disabled { color: #aaa; background: #f0f0f2; }
            QPushButton#primary {
                background: #0b5ed7; color: #ffffff; border: none; font-weight: 600;
                text-align: center;
            }
            QPushButton#primary:hover:enabled { background: #0a52bd; }
            QPushButton#primary:disabled { background: #b9c6dd; color: #eef; }
            """
        )

    # ------------------------------------------------------------- closing
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.scan_view.stop()
        super().closeEvent(event)


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
