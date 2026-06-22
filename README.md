# Attendance Taking

A fully-local Windows desktop application for event registration. Registration
staff upload an Excel sheet of expected participants, scan each participant's QR
code with a webcam to register attendance, and then generate a PowerPoint deck in
which every present and absent attendee is inserted as a filled slide under the
correct per-grade section heading.

Every change is auto-saved to a local database the instant it happens, so an
accidental exit (or a crash) never loses data. Nothing leaves the machine — there
are no network calls.

This document is both an **end-user manual** and a **developer hand-over guide**.
The first half (Sections 1–6) is for operators; the second half (Sections 7–13)
is for developers maintaining or extending the app.

---

## Table of contents

1. [What the app does](#1-what-the-app-does)
2. [Requirements](#2-requirements)
3. [Installation](#3-installation)
4. [Running the app](#4-running-the-app)
5. [Operator workflow (step by step)](#5-operator-workflow-step-by-step)
6. [Outputs, persistence, and clearing data](#6-outputs-persistence-and-clearing-data)
7. [Architecture overview](#7-architecture-overview)
8. [Project layout](#8-project-layout)
9. [Data model (SQLite)](#9-data-model-sqlite)
10. [How key features work internally](#10-how-key-features-work-internally)
11. [Testing](#11-testing)
12. [Extending the app](#12-extending-the-app)
13. [Troubleshooting & known limitations](#13-troubleshooting--known-limitations)

---

## 1. What the app does

| Capability | Detail |
|---|---|
| Roster import | Reads an `.xlsx`/`.xlsm` of expected participants. Required columns (case/whitespace tolerant): `unique qr id`, `name`, `title`, `grade`. Any extra columns are preserved in the output. |
| QR scanning | Uses the default webcam and OpenCV's built-in QR detector. The QR must encode the participant's `unique qr id` **verbatim**. |
| Scan feedback | Green = checked in. Amber = already checked in (no double counting). Red = unknown QR (not on the roster — rejected). |
| Deck population | Clones a per-grade *template* slide for each attendee, fills in their name and title, and inserts it after that grade's *section title* slide. Present and absent attendees are handled separately, per grade. |
| Auto-save | The SQLite database is committed on every scan, upload, mapping change, and clear. The attendance Excel is regenerated on every successful scan. |
| Safe clearing | Each piece of data has its own clear button, each behind a confirmation dialog. |

The grade values are **dynamic** — whatever distinct values appear in the roster's
`grade` column become the grades the app maps and groups by (e.g. `e`, `m`, `f`).

---

## 2. Requirements

- **Windows** (file-open uses `os.startfile`; the scanner prefers the DirectShow
  camera backend).
- A **webcam**.
- **Python 3.11 or newer** installed and available on `PATH`.
  - Verified working on Python **3.14.6**. Note that 3.14 is very new; if a future
    dependency upgrade has no 3.14 wheel, Python **3.12** is the safest fallback.
- **PowerPoint** (or any `.pptx`-compatible viewer) to open the generated deck.
- **Excel** (or compatible) to open the attendance workbook.

Python dependencies (installed into the project venv by the setup script):

| Package | Purpose |
|---|---|
| `PySide6` | Qt-based GUI |
| `opencv-python` | Webcam capture + `cv2.QRCodeDetector` decoding |
| `openpyxl` | Read/write Excel workbooks |
| `python-pptx` | Read/clone/fill/write PowerPoint decks |

`sqlite3` ships with Python's standard library.

---

## 3. Installation

From the project root, run **once**:

```powershell
.\setup.ps1
```

(or `setup.bat` from `cmd`). This:

1. Creates an isolated virtual environment in `.\.venv`.
2. Upgrades `pip`.
3. Installs everything in `requirements.txt`.

If `python` resolves to the Microsoft Store stub instead of a real interpreter,
install Python from python.org (tick **“Add python.exe to PATH”**), restart the
terminal, and re-run `setup.ps1`.

---

## 4. Running the app

```powershell
.\run.ps1
```

(or `run.bat`, or directly `.\.venv\Scripts\python.exe main.py`).

The window opens with a control panel on the left and the live scanning view on
the right. Buttons are greyed out until their prerequisites are met (see below).

---

## 5. Operator workflow (step by step)

The left panel is organised into three numbered steps plus a clear-data section.

### Step 1 — Data sources

1. **Upload expected participants (Excel)…**
   - Pick the roster `.xlsx`. The required columns are matched ignoring case and
     surrounding spaces, so `Unique QR ID`, `unique qr id`, etc. all work.
   - The file is validated (missing columns, blank IDs, or duplicate IDs are
     reported) and **copied into `data/`**. An initial all-absent attendance
     workbook is written immediately.
   - ✅ Enables scanning.

2. **Upload template deck (.pptx)…**
   - Pick your PowerPoint template. It is copied into `data/`.
   - ✅ Enables “Configure slide mappings”.

3. **Configure slide mappings…**
   - The dialog lists **every distinct grade** found in the roster. For each grade
     you choose four slides from drop-downs (each entry shows the slide number and
     its title text):
     - **Present → Title slide**: the “_X grade attendees_” heading.
     - **Present → Template slide**: the per-attendee layout to clone for present people.
     - **Absent → Title slide**: the “_X grade absentees_” heading.
     - **Absent → Template slide**: the per-attendee layout to clone for absent people.
   - For each **template** slide, click **Set shapes…** and choose which text box
     holds the **name** and which holds the **title**. (The picker lists each text
     box by its shape name and a snippet of its current text.) The button shows
     “Shapes set ✓” once both are chosen.
   - Click **Save**. Mappings are stored in the database and survive restarts.
   - ✅ When *every* grade has all four slides mapped **and** both template shapes
     designated, “Populate slide deck” is enabled.

### Step 2 — Attendance

4. **Start scanning** — opens the webcam. Present a participant's QR code:
   - **Green banner**: checked in — shows name and title.
   - **Amber banner**: already checked in — no change, no double count.
   - **Red banner**: the QR value is not on the roster — rejected.
   - The same QR is ignored for a few seconds after a read (debounce) so holding it
     up doesn't fire repeatedly.
   - Click **Stop scanning** to release the camera.
   - The attendance Excel is re-saved after every successful check-in.

5. **Open attendance excel** — opens the current `data/attendance.xlsx`.

### Step 3 — Slide deck

6. **Populate slide deck** — builds the deck (see §10.3) and saves a new
   **timestamped** file in `data/`. You're offered the option to open it
   immediately. You can press this at any time, as often as you like; each press
   reflects the current attendance and produces a fresh file.

### Clear data (each with confirmation)

- **Clear attendance** — resets all check-ins to absent; keeps roster + mappings.
- **Clear slide mappings** — deletes all slide mappings only.
- **Clear template deck** — removes the template **and** its mappings.
- **Clear expected participants** — removes the roster **and** its attendance and
  mappings (they depend on it).

---

## 6. Outputs, persistence, and clearing data

All working data lives in **`data/`** (created automatically; git-ignored):

| File | Description |
|---|---|
| `app.db` | SQLite database — the **single source of truth**. |
| `expected_participants.xlsx` | A copy of the uploaded roster (keeps the app self-contained). |
| `template_deck.pptx` | A copy of the uploaded template. |
| `attendance.xlsx` | All original roster columns **+ a `Status` column** (`Present`/`Absent`), in the **original input row order**. Regenerated on every scan and on demand. |
| `attendance_deck_YYYY-MM-DD_HHMMSS.pptx` | A populated deck, one file per generation. |

**Crash safety:** every mutating action is a single committed SQLite transaction,
so closing the app (deliberately or accidentally) at any point never loses
already-recorded data. On next launch the app reloads the roster, template,
mappings, and check-ins from `app.db`.

> Deleting the `data/` folder is a hard reset — it wipes everything. Prefer the
> in-app clear buttons for partial resets.

---

## 7. Architecture overview

The app is a single-process PySide6 (Qt) desktop application. There are three
layers:

```
            ┌──────────────────────────── ui/ ────────────────────────────┐
            │ MainWindow  ──  ScanView      MappingDialog   ShapePicker     │
            └───────┬───────────┬────────────────┬──────────────┬──────────┘
                    │           │ frames/decodes │              │
            ┌───────▼───────────▼────────────────▼──────────────▼──────────┐
            │ app/  Database   ScannerThread   excel_io   pptx_builder      │
            │       (SQLite)   (QThread+cv2)   (openpyxl) (python-pptx)     │
            │                                   pptx_utils (XML helpers)    │
            └───────────────────────────────────────┬──────────────────────┘
                                                     │
                                            data/app.db  +  data/*.xlsx/.pptx
```

- **`ui/`** holds only presentation and user-interaction logic. It calls into
  `app/` for all real work.
- **`app/`** holds the business/IO logic with no Qt dependencies *except*
  `scanner.py`, which subclasses `QThread` to stream webcam frames safely off the
  UI thread.
- The **`Database`** object is created once in `main.py` and passed into the UI.
  It is the source of truth; Excel/PowerPoint files are derived artifacts.

Key design decisions and the reasoning behind them are recorded in
`C:\Users\Work\.claude\plans\create-an-attendance-taking-squishy-sketch.md`.

---

## 8. Project layout

```
msspc/
├─ main.py                 # Entry point: QApplication + Database + MainWindow
├─ requirements.txt
├─ setup.ps1 / setup.bat   # Create .venv and install dependencies
├─ run.ps1   / run.bat     # Launch via the venv
├─ README.md
├─ app/
│  ├─ config.py            # Paths, filenames, column names, constants
│  ├─ db.py                # SQLite schema + atomic CRUD (Database, Participant)
│  ├─ excel_io.py          # import_participants(), export_attendance()
│  ├─ scanner.py           # ScannerThread: webcam frames + QR decode (QThread)
│  ├─ pptx_utils.py        # Slide clone/move/delete + shape helpers + inspection
│  └─ pptx_builder.py      # build_deck(): assemble the populated deck
├─ ui/
│  ├─ main_window.py       # Control panel, gating, wiring, clear buttons
│  ├─ scan_view.py         # Live camera widget + colored result banner
│  ├─ mapping_dialog.py    # Per-grade 4-slide mapping
│  └─ shape_picker.py      # Pick name/title shapes on a template slide
├─ tests/
│  ├─ make_samples.py      # Generate a sample roster + template deck
│  ├─ test_pipeline.py     # Headless db+excel+pptx end-to-end assertions
│  └─ test_gui_smoke.py    # Offscreen GUI construction + gating checks
├─ data/                   # Working folder (git-ignored): app.db + artifacts
└─ .venv/                  # Virtual environment (git-ignored)
```

---

## 9. Data model (SQLite)

Database file: `data/app.db` (WAL mode, foreign keys on). Defined in
`app/db.py :: Database.init_schema`.

### `participants`
| Column | Type | Notes |
|---|---|---|
| `qr_id` | TEXT PK | The value the QR code must encode. |
| `name` | TEXT | |
| `title` | TEXT | Shown on the slide. |
| `grade` | TEXT | Drives sectioning; values are whatever the roster contains. |
| `row_index` | INTEGER | 0-based original Excel row order (defines output ordering). |
| `present` | INTEGER | 0 = absent, 1 = present. |
| `checkin_time` | TEXT | `YYYY-MM-DD HH:MM:SS` when marked present, else NULL. |

### `meta` (key/value)
- `expected_xlsx` → path to the copied roster.
- `template_pptx` → path to the copied template.

### `slide_mappings`
Primary key `(grade, role, kind)`.
| Column | Notes |
|---|---|
| `grade` | A roster grade. |
| `role` | `present` or `absent`. |
| `kind` | `title` (section heading slide) or `template` (per-attendee slide). |
| `slide_idx` | 0-based slide index in the **original** template deck. |
| `name_shape_id` | Shape id of the name text box (template rows only). |
| `title_shape_id` | Shape id of the title text box (template rows only). |

`Database.mappings_complete()` returns `True` only when every distinct grade has
all four `(role, kind)` rows **and** both template rows have name+title shape ids.
This is the gate for the **Populate** button.

---

## 10. How key features work internally

### 10.1 Roster import (`app/excel_io.py :: import_participants`)
- Opens the workbook read-only; matches the four required headers
  case/whitespace-insensitively (`_find_required_columns`).
- Skips fully blank rows; raises `ExcelError` on a missing/blank `unique qr id` or
  a duplicate id.
- Copies the original file to `config.EXPECTED_XLSX`, then atomically replaces the
  `participants` table (`Database.replace_participants`) — which also clears any
  prior attendance, because a new roster invalidates old check-ins.

### 10.2 Attendance export (`app/excel_io.py :: export_attendance`)
- Re-reads the **copied original** roster so all original columns and ordering are
  preserved exactly.
- Appends a `Status` column, filling `Present`/`Absent` per `participants.present`,
  matched by the `unique qr id` cell. Writes `data/attendance.xlsx`.
- Called after every successful scan and after “Clear attendance”.

### 10.3 Deck population (`app/pptx_builder.py` + `app/pptx_utils.py`)
This is the most intricate part, because **python-pptx has no public API to
duplicate, reorder, or delete slides**. The helpers in `pptx_utils.py` implement
those at the XML/relationship level:

- **`duplicate_slide(prs, src_slide)`** — adds a slide on the source's layout,
  removes the auto-inserted layout placeholders, deep-copies every shape element
  from the source, then **re-creates the source's relationships** (images, media,
  hyperlinks) on the new slide. Because python-pptx assigns *fresh* relationship
  ids, the function builds an old→new rId map and rewrites the matching
  `r:embed`/`r:link` attributes inside the copied XML — so pictures and links
  survive the clone. (The slide-layout relationship is skipped; the new slide
  already has its own.)
- **`move_slide_to(prs, slide, new_index)`** — reorders by moving the slide's
  `<p:sldId>` element within `prs.slides._sldIdLst`.
- **`delete_slide(prs, slide_element)`** — removes the matching `<p:sldId>` and
  pops the presentation→slide relationship (`rels.pop(rId)`).
- **`find_shape_by_id` / `set_shape_text`** — locate the mapped shape on a clone
  and set its text while preserving the template's font/size/colour (only the
  first run's text is replaced; extra runs/paragraphs are removed).
- **Inspection helpers** (`list_slides`, `list_text_shapes`, `slide_title_text`)
  feed the mapping UI and shape picker.

`build_deck(db, out_path)` then:

1. Loads a fresh copy of the original template (so generations never accumulate).
2. Captures stable references to the original slide objects up front, because
   inserting clones shifts indices.
3. For each grade × role, gathers the matching participants **in `row_index`
   order**, clones the template slide for each, fills name + title, and moves each
   clone to sit immediately after that section's title slide (consecutively, in
   order).
4. Removes the now-redundant template source slides.
5. Saves to the timestamped path.

The result, per grade, is: title slide → present attendees, then absent title
slide → absent attendees, all in input-roster order.

### 10.4 Scanning (`app/scanner.py` + `ui/scan_view.py`)
- `ScannerThread` (a `QThread`) opens the default camera (DirectShow backend with
  a default-backend fallback), reads frames in a loop, emits each frame for live
  preview (`frame_ready`) and emits decoded QR strings (`qr_decoded`) through Qt
  signals. A debounce (`config.SCAN_DEBOUNCE_SECONDS`, default 3 s) suppresses
  repeated reads of the same code.
- `ScanView` renders frames into a `QLabel` and shows a colour-coded banner. It
  calls back into `MainWindow._handle_decode(value)`, which validates against the
  roster, updates the DB, regenerates the attendance Excel, and returns a
  `(level, message)` tuple (`ok`/`warn`/`error`) that drives the banner colour.

### 10.5 Button gating (`ui/main_window.py :: _refresh_state`)
Recomputed after every relevant action:
- Mappings button: enabled when roster **and** template are present.
- Scan button: enabled when a roster is loaded.
- Populate button: enabled when a template is loaded **and** `mappings_complete()`.
- Open-attendance: enabled when `attendance.xlsx` exists.
- Each clear button: enabled only when there is something to clear.

---

## 11. Testing

The venv's Python is required (`.\.venv\Scripts\python.exe`).

```powershell
# Generate sample roster + template into tests\sample_data\
.\.venv\Scripts\python.exe tests\make_samples.py

# Headless end-to-end: db + excel + pptx engine, with assertions
.\.venv\Scripts\python.exe tests\test_pipeline.py

# Offscreen GUI: constructs MainWindow + dialogs, checks button gating
.\.venv\Scripts\python.exe tests\test_gui_smoke.py
```

- **`test_pipeline.py`** imports a sample roster, programmatically maps slides,
  marks some people present, exports the attendance workbook (asserting columns,
  `Status`, and input ordering), builds the deck, and asserts that each attendee
  appears under the correct section in the correct order with no leftover
  `{{name}}`/`{{title}}` tokens. This is the primary regression guard for the
  slide engine.
- **`test_gui_smoke.py`** runs with `QT_QPA_PLATFORM=offscreen`, builds the main
  window and both dialogs against the sample data, and verifies the gating logic.
  (It prints a harmless “Cannot find font directory” warning under the offscreen
  Qt plugin.)

**Not covered by automated tests:** the live webcam decode loop — it needs a real
camera and a physical/displayed QR. Verify it manually (see §13).

The sample template created by `make_samples.py` builds, per grade, an
attendees-title slide, an attendees-template slide (with `NAME` and `TITLE` text
boxes), an absentees-title slide, and an absentees-template slide — a faithful
model of what an operator's real template should contain.

---

## 12. Extending the app

Some common changes and where to make them:

| Goal | Where |
|---|---|
| Change required column names | `app/config.py` (`COL_*`, `REQUIRED_COLUMNS`); matching is in `excel_io._find_required_columns`. |
| Add columns to the attendance export | `app/excel_io.py :: export_attendance`. |
| Change scan debounce or camera index | `config.SCAN_DEBOUNCE_SECONDS`; `ScannerThread(camera_index=...)`. |
| Add fields to a slide (e.g. department) | Extend `slide_mappings` with another `*_shape_id`, capture it in `ui/shape_picker.py` + `ui/mapping_dialog.py`, and fill it in `pptx_builder.build_deck`. |
| Different attendee ordering | `build_deck` already orders by `row_index`; change the sort there. |
| Keep template slides in the output | Remove the `delete_slide` loop in `build_deck`. |
| Switch QR decoder to `pyzbar` | Replace the `cv2.QRCodeDetector` calls in `app/scanner.py` (add `pyzbar` + the zbar runtime). |
| Restyle the UI | The Qt stylesheet lives in `MainWindow._apply_style`; banner colours in `ScanView._banner_style`. |

Conventions to keep:
- Keep Qt out of `app/` (except `scanner.py`). UI talks to `app/`, not vice versa.
- Treat `app.db` as the source of truth; regenerate derived files from it.
- Wrap DB mutations so they commit immediately (preserve crash-safety).

---

## 13. Troubleshooting & known limitations

**`python` opens the Microsoft Store / “Python was not found”.**
The Store alias is shadowing a real interpreter (or none is installed). Install
Python from python.org with “Add to PATH”, restart the terminal, re-run setup.

**Camera won't open / “Could not open the webcam.”**
Another app may be using it, or there's no camera. Close other camera apps; check
Windows camera privacy settings. To target a non-default camera, change
`camera_index` where `ScannerThread` is created in `ui/scan_view.py`.

**QR codes don't decode.**
`cv2.QRCodeDetector` is sensitive to focus/lighting/size. Improve lighting, hold
the code steadier and larger in frame. For tougher cases, switch to `pyzbar`
(see §12).

**Populate is greyed out.**
Either no template is loaded or the mappings are incomplete. Open “Configure slide
mappings” and ensure every grade has all four slides chosen and both template
shapes set (`mappings_complete()` must be true).

**Generated deck looks wrong (extra/blank slide, wrong text box filled).**
Re-check the mapping: the *template* slide must be the per-attendee layout (not the
title slide), and the name/title shapes must point at the correct text boxes.

**A font warning appears when running tests.**
Only under the offscreen Qt platform used by `test_gui_smoke.py`; harmless and does
not occur in normal GUI use.

**Known limitations.**
- Windows-oriented (`os.startfile`, DirectShow camera backend).
- Single default camera at a time; no in-app camera picker (index is code-level).
- python-pptx slide cloning is XML-level; very exotic template constructs (embedded
  OLE objects, charts with external data) are not specifically handled — plain
  text boxes, pictures, and standard shapes are.
- Manual verification is required for the live camera path.

### Quick manual end-to-end check
1. `.\setup.ps1` then `.\run.ps1`.
2. `.\.venv\Scripts\python.exe tests\make_samples.py` to create sample files.
3. Upload `tests\sample_data\participants.xlsx` and `tests\sample_data\template.pptx`.
4. Configure mappings for grades `e`, `m`, `f` (set the name/title shapes on each
   template slide).
5. Start scanning and present a QR encoding e.g. `E001` → green check-in; present it
   again → amber; present a bogus code → red.
6. Open the attendance Excel; confirm `Status` and original ordering.
7. Populate the deck; confirm attendees appear under the right sections in roster
   order with names and titles filled in.
