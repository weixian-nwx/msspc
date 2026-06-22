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

    # Construct the mapping dialog against sample data.
    import tests.make_samples as samples
    from app.excel_io import import_participants
    from ui.mapping_dialog import MappingDialog

    samples.make_excel()
    samples.make_pptx()
    import_participants(samples.XLSX, db)
    db.set_meta("template_pptx", samples.PPTX)

    md = MappingDialog(db, samples.PPTX)
    md.show()
    app.processEvents()
    assert set(md.rows.keys()) == {"e", "m", "f"}, md.rows.keys()
    print("  MappingDialog built with grades:", sorted(md.rows.keys()))

    # The inline shape dropdowns must list the chosen template slide's text
    # boxes, and repopulate when the template slide changes. Slide 1 is a
    # template slide in the sample deck.
    row = md.rows["m"]
    tmpl_combo = row.combos[(config.ROLE_PRESENT, config.KIND_TEMPLATE)]
    tmpl_combo.setCurrentIndex(tmpl_combo.findData(1))
    app.processEvents()
    name_count = row.name_combos[config.ROLE_PRESENT].count()
    assert name_count >= 2, "inline name dropdown should list the template slide's text boxes"
    print("  inline shape dropdown listed", name_count, "shapes")
    md.close()

    # Manual attendance toggle: emitting toggle_requested routes to the handler,
    # which (with confirmation forced) marks the participant present, mirroring a
    # scan. _confirm shows a blocking dialog, so stub it to auto-accept.
    w._confirm = lambda *a, **k: True
    before_present, _ = db.counts()
    qr = db.all_participants()[0].qr_id
    w.participant_list.toggle_requested.emit(qr)
    app.processEvents()
    assert db.get_participant(qr).present, "double-click toggle should mark present"
    assert db.counts()[0] == before_present + 1, "present count should rise by one"
    w.participant_list.toggle_requested.emit(qr)  # toggle back to absent
    app.processEvents()
    assert not db.get_participant(qr).present, "second toggle should mark absent"
    assert db.counts()[0] == before_present, "present count should return to baseline"
    print("  manual toggle marks present then absent OK")

    w.close()
    db.close()
    os.remove(os.path.join(config.DATA_DIR, "smoke.db"))
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
