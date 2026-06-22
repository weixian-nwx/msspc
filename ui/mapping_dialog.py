"""Per-grade slide mapping dialog.

For every distinct grade found in the roster the user selects four slides:
present-title, present-template, absent-title, absent-template. For the two
template slides they also designate the name/title shapes (via ShapePicker).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.db import Database
from app.pptx_utils import list_slides
from ui.shape_picker import ShapePickerDialog


class _GradeRow:
    """Holds the widgets and shape selections for one grade."""

    def __init__(self, grade: str) -> None:
        self.grade = grade
        self.combos: dict[tuple[str, str], QComboBox] = {}
        # (role) -> (name_shape_id, title_shape_id)
        self.shapes: dict[str, tuple[int | None, int | None]] = {
            config.ROLE_PRESENT: (None, None),
            config.ROLE_ABSENT: (None, None),
        }
        self.shape_buttons: dict[str, QPushButton] = {}


class MappingDialog(QDialog):
    def __init__(self, db: Database, pptx_path: str, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.pptx_path = pptx_path
        self.setWindowTitle("Configure slide mappings")
        self.setMinimumSize(720, 520)

        self.slides = list_slides(pptx_path)  # [{idx, title}]
        self.grades = db.distinct_grades()
        self.rows: dict[str, _GradeRow] = {}

        outer = QVBoxLayout(self)
        outer.addWidget(
            QLabel(
                "For each grade, choose the section <b>title</b> slide (where attendees are "
                "inserted after) and the per-attendee <b>template</b> slide (cloned and filled)."
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        for grade in self.grades:
            container_layout.addWidget(self._build_grade_group(grade))
        container_layout.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._load_existing()

    # ------------------------------------------------------------- UI build
    def _build_grade_group(self, grade: str) -> QGroupBox:
        row = _GradeRow(grade)
        self.rows[grade] = row

        box = QGroupBox(f"Grade: {grade}")
        grid = QGridLayout(box)
        grid.addWidget(QLabel("<b>Present</b>"), 0, 1)
        grid.addWidget(QLabel("<b>Absent</b>"), 0, 2)

        grid.addWidget(QLabel("Title slide:"), 1, 0)
        grid.addWidget(QLabel("Template slide:"), 2, 0)
        grid.addWidget(QLabel("Name / Title shapes:"), 3, 0)

        for col, role in enumerate((config.ROLE_PRESENT, config.ROLE_ABSENT), start=1):
            title_combo = self._slide_combo()
            tmpl_combo = self._slide_combo()
            row.combos[(role, config.KIND_TITLE)] = title_combo
            row.combos[(role, config.KIND_TEMPLATE)] = tmpl_combo
            grid.addWidget(title_combo, 1, col)
            grid.addWidget(tmpl_combo, 2, col)

            shape_btn = QPushButton("Set shapes…")
            shape_btn.clicked.connect(lambda _=False, g=grade, r=role: self._pick_shapes(g, r))
            row.shape_buttons[role] = shape_btn
            grid.addWidget(shape_btn, 3, col)

        return box

    def _slide_combo(self) -> QComboBox:
        combo = QComboBox()
        for s in self.slides:
            combo.addItem(f'{s["idx"] + 1}. {s["title"]}', s["idx"])
        return combo

    # ----------------------------------------------------------- behaviour
    def _pick_shapes(self, grade: str, role: str) -> None:
        row = self.rows[grade]
        tmpl_combo = row.combos[(role, config.KIND_TEMPLATE)]
        slide_idx = tmpl_combo.currentData()
        cur_name, cur_title = row.shapes[role]
        dlg = ShapePickerDialog(self.pptx_path, slide_idx, cur_name, cur_title, self)
        if dlg.exec() == QDialog.Accepted:
            row.shapes[role] = (dlg.selected_name_id(), dlg.selected_title_id())
            self._refresh_shape_button(grade, role)

    def _refresh_shape_button(self, grade: str, role: str) -> None:
        row = self.rows[grade]
        name_id, title_id = row.shapes[role]
        if name_id is not None and title_id is not None:
            row.shape_buttons[role].setText("Shapes set ✓")
        else:
            row.shape_buttons[role].setText("Set shapes…")

    def _load_existing(self) -> None:
        """Pre-populate from any previously saved mappings."""
        for grade in self.grades:
            row = self.rows[grade]
            for role in config.ROLES:
                for kind in config.KINDS:
                    m = self.db.get_mapping(grade, role, kind)
                    if not m:
                        continue
                    combo = row.combos[(role, kind)]
                    idx = combo.findData(m["slide_idx"])
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    if kind == config.KIND_TEMPLATE:
                        row.shapes[role] = (m["name_shape_id"], m["title_shape_id"])
                self._refresh_shape_button(grade, role)

    def _on_save(self) -> None:
        # Validate: every grade needs both template shapes designated.
        for grade in self.grades:
            row = self.rows[grade]
            for role in config.ROLES:
                name_id, title_id = row.shapes[role]
                if name_id is None or title_id is None:
                    QMessageBox.warning(
                        self,
                        "Shapes not set",
                        f"Please set the name & title shapes for grade '{grade}' ({role}).",
                    )
                    return

        for grade in self.grades:
            row = self.rows[grade]
            for role in config.ROLES:
                name_id, title_id = row.shapes[role]
                self.db.save_mapping(
                    grade,
                    role,
                    config.KIND_TITLE,
                    row.combos[(role, config.KIND_TITLE)].currentData(),
                )
                self.db.save_mapping(
                    grade,
                    role,
                    config.KIND_TEMPLATE,
                    row.combos[(role, config.KIND_TEMPLATE)].currentData(),
                    name_id,
                    title_id,
                )
        self.accept()
