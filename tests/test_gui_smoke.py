"""Offscreen GUI smoke test: construct the main window without a camera.

Run with QT_QPA_PLATFORM=offscreen and the project venv python.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.db import Database  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    config.ensure_data_dir()
    app = QApplication([])
    db = Database(os.path.join(config.DATA_DIR, "smoke.db"))
    db.init_schema()
    w = MainWindow(db)
    w.show()
    app.processEvents()

    print("MainWindow constructed OK")
    print("  scan enabled (no excel):", w.btn_scan.isEnabled())
    print("  populate enabled (no template):", w.btn_populate.isEnabled())
    print("  mappings enabled:", w.btn_mappings.isEnabled())

    assert not w.btn_scan.isEnabled(), "scan must be disabled with no roster"
    assert not w.btn_populate.isEnabled(), "populate must be disabled with no template"
    assert not w.btn_mappings.isEnabled(), "mappings must be disabled with no template"

    # Construct the mapping dialog + shape picker against sample data.
    import tests.make_samples as samples
    from app.excel_io import import_participants
    from app.pptx_utils import list_text_shapes
    from ui.mapping_dialog import MappingDialog
    from ui.shape_picker import ShapePickerDialog

    samples.make_excel()
    samples.make_pptx()
    import_participants(samples.XLSX, db)
    db.set_meta("template_pptx", samples.PPTX)

    md = MappingDialog(db, samples.PPTX)
    md.show()
    app.processEvents()
    assert set(md.rows.keys()) == {"e", "m", "f"}, md.rows.keys()
    print("  MappingDialog built with grades:", sorted(md.rows.keys()))
    md.close()

    sp = ShapePickerDialog(samples.PPTX, 1)  # slide 1 is a template slide
    sp.show()
    app.processEvents()
    assert sp.name_combo.count() >= 2, "shape picker should list the text boxes"
    print("  ShapePickerDialog listed", sp.name_combo.count(), "shapes")
    sp.close()

    w.close()
    db.close()
    os.remove(os.path.join(config.DATA_DIR, "smoke.db"))
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
