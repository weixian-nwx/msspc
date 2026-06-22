"""Dialog to designate which shapes on a template slide hold name and title."""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from app.pptx_utils import list_text_shapes


class ShapePickerDialog(QDialog):
    """Pick the name-shape and title-shape from a slide's text shapes."""

    def __init__(
        self,
        pptx_path: str,
        slide_idx: int,
        current_name_id: Optional[int] = None,
        current_title_id: Optional[int] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select name & title shapes")
        self.setMinimumWidth(460)

        self._shapes = list_text_shapes(pptx_path, slide_idx)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Choose which text box on this template slide holds the attendee's "
                "<b>name</b> and which holds the <b>title</b>."
            )
        )

        if not self._shapes:
            layout.addWidget(QLabel("<i>This slide has no text boxes to map.</i>"))

        layout.addWidget(QLabel("Name shape:"))
        self.name_combo = QComboBox()
        self._fill_combo(self.name_combo, current_name_id)
        layout.addWidget(self.name_combo)

        layout.addWidget(QLabel("Title shape:"))
        self.title_combo = QComboBox()
        self._fill_combo(self.title_combo, current_title_id)
        layout.addWidget(self.title_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill_combo(self, combo: QComboBox, current_id: Optional[int]) -> None:
        for s in self._shapes:
            text = s["text"].replace("\n", " ")
            if len(text) > 40:
                text = text[:37] + "..."
            label = f'{s["name"]}  —  "{text}"' if text else s["name"]
            combo.addItem(label, s["shape_id"])
        if current_id is not None:
            idx = combo.findData(current_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def selected_name_id(self) -> Optional[int]:
        return self.name_combo.currentData()

    def selected_title_id(self) -> Optional[int]:
        return self.title_combo.currentData()
