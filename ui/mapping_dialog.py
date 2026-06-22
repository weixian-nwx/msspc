"""Per-grade slide mapping dialog.

For every distinct grade found in the roster the user selects four slides:
present-title, present-template, absent-title, absent-template. For the two
template slides they also designate the name/title shapes, picked inline from
dropdowns that list the chosen template slide's own text boxes.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.db import Database
from app.pptx_utils import list_slides, list_text_shapes


class _GradeRow:
    """Holds the widgets for one grade."""

    def __init__(self, grade: str) -> None:
        self.grade = grade
        self.combos: dict[tuple[str, str], QComboBox] = {}
        # (role) -> shape combos, populated from the chosen template slide.
        self.name_combos: dict[str, QComboBox] = {}
        self.title_combos: dict[str, QComboBox] = {}


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
        self._shape_cache: dict[int, list[dict]] = {}

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
        # The two shape rows are indented so they visibly belong to the
        # template slide above them — their options come from that slide.
        grid.addWidget(QLabel(" ↳ Name shape:"), 3, 0)
        grid.addWidget(QLabel(" ↳ Title shape:"), 4, 0)

        for col, role in enumerate((config.ROLE_PRESENT, config.ROLE_ABSENT), start=1):
            title_combo = self._slide_combo()
            tmpl_combo = self._slide_combo()
            row.combos[(role, config.KIND_TITLE)] = title_combo
            row.combos[(role, config.KIND_TEMPLATE)] = tmpl_combo
            grid.addWidget(title_combo, 1, col)
            grid.addWidget(tmpl_combo, 2, col)

            name_combo = QComboBox()
            title_shape_combo = QComboBox()
            row.name_combos[role] = name_combo
            row.title_combos[role] = title_shape_combo
            grid.addWidget(name_combo, 3, col)
            grid.addWidget(title_shape_combo, 4, col)

            # Seed the shape dropdowns from the template combo's default slide,
            # then react to later changes (which clears any stale selection).
            self._populate_shapes(role, tmpl_combo.currentData(), name_combo, title_shape_combo)
            tmpl_combo.currentIndexChanged.connect(
                lambda _=0, g=grade, r=role: self._on_template_changed(g, r)
            )

        return box

    def _slide_combo(self) -> QComboBox:
        combo = QComboBox()
        for s in self.slides:
            combo.addItem(f'{s["idx"] + 1}. {s["title"]}', s["idx"])
        return combo

    # ----------------------------------------------------------- behaviour
    def _text_shapes(self, slide_idx: int) -> list[dict]:
        """Cached text-shape listing for a slide (avoids re-opening the pptx)."""
        if slide_idx not in self._shape_cache:
            self._shape_cache[slide_idx] = list_text_shapes(self.pptx_path, slide_idx)
        return self._shape_cache[slide_idx]

    @staticmethod
    def _shape_label(shape: dict) -> str:
        text = shape["text"].replace("\n", " ")
        if len(text) > 40:
            text = text[:37] + "..."
        return f'{shape["name"]}  —  "{text}"' if text else shape["name"]

    def _populate_shapes(
        self,
        role: str,
        slide_idx: int | None,
        name_combo: QComboBox,
        title_combo: QComboBox,
        name_id: int | None = None,
        title_id: int | None = None,
    ) -> None:
        """Fill both shape combos from ``slide_idx``'s text boxes.

        Rebuilding the lists drops any prior pick that isn't on the new slide,
        which is exactly the reset we want when the template slide changes.
        ``name_id`` / ``title_id`` re-select a saved shape when restoring.
        """
        shapes = self._text_shapes(slide_idx) if slide_idx is not None else []
        for combo, want in ((name_combo, name_id), (title_combo, title_id)):
            combo.clear()
            for s in shapes:
                combo.addItem(self._shape_label(s), s["shape_id"])
            if want is not None:
                idx = combo.findData(want)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def _on_template_changed(self, grade: str, role: str) -> None:
        row = self.rows[grade]
        slide_idx = row.combos[(role, config.KIND_TEMPLATE)].currentData()
        self._populate_shapes(
            role, slide_idx, row.name_combos[role], row.title_combos[role]
        )

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
                        # Re-fill the shape combos for this slide and re-select
                        # the saved shapes. (Setting the template index above may
                        # not emit a change if it was already the default slide.)
                        self._populate_shapes(
                            role,
                            m["slide_idx"],
                            row.name_combos[role],
                            row.title_combos[role],
                            m["name_shape_id"],
                            m["title_shape_id"],
                        )

    def _on_save(self) -> None:
        # Validate: every grade needs both template shapes designated.
        for grade in self.grades:
            row = self.rows[grade]
            for role in config.ROLES:
                if (
                    row.name_combos[role].currentData() is None
                    or row.title_combos[role].currentData() is None
                ):
                    QMessageBox.warning(
                        self,
                        "Shapes not set",
                        f"Please set the name & title shapes for grade '{grade}' ({role}).",
                    )
                    return

        for grade in self.grades:
            row = self.rows[grade]
            for role in config.ROLES:
                name_id = row.name_combos[role].currentData()
                title_id = row.title_combos[role].currentData()
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
