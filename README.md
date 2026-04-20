# Fillable PDF Creator

A desktop GUI application that lets you open any PDF, detect blank form fields automatically, place additional fields by drawing on the page, and save a standard AcroForm-compliant fillable PDF.

## Features

- **Open any PDF** — render and display at full quality
- **Auto-detect blank fields** — finds underscores, horizontal lines, and empty boxes and converts them into interactive form fields
- **Draw new fields** — drag on the canvas to place text fields, checkboxes, radio buttons, or dropdowns
- **Select, move & resize** — click a field to select it, then drag the body to move it or drag a handle to resize it
- **Copy & paste** — `Ctrl+C` / `Ctrl+V` (or the sidebar button) duplicates a selected field; repeated pastes cascade so fields don't stack
- **Edit properties** — rename a field or set its default value via the sidebar properties panel
- **Multi-page support** — navigate between pages; fields are tracked per-page
- **Save fillable PDF** — writes a standard AcroForm PDF readable by Acrobat, browsers, and any compliant viewer

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`:
  - [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) ≥ 1.23
  - [customtkinter](https://github.com/TomSchimansky/CustomTkinter) ≥ 5.2
  - [Pillow](https://python-pillow.org/) ≥ 10.0

## Installation

```bash
# Clone or download the project
cd FillablePDF

# Create and activate a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the App

```bash
python main.py
```

## Quick User Manual

### 1 — Open a PDF
Click **Open PDF** in the toolbar and choose any PDF file. The first page renders immediately; use the **◀ / ▶** navigation buttons to move between pages.

### 2 — Auto-Detect Fields
Click **Auto-Detect Fields** to scan the current page. The app finds underscores, horizontal lines, and empty boxes and converts them into text fields automatically. Detected fields appear as blue overlays on the canvas.

### 3 — Add Fields Manually
Pick a field type from the sidebar:

| Button | Field type |
|---|---|
| Text Field | Single-line text input |
| Checkbox | Boolean tick box |
| Radio Button | Single-selection button |
| Dropdown | Combo-box with selectable options |

Then **click and drag** on the canvas to draw the field at the size and position you want.

### 4 — Select, Move & Resize
Switch to **Select / Move** mode (top of sidebar). Then:
- **Click** a field to select it (turns red).
- **Drag the body** to reposition it.
- **Drag a handle** (corners or edge midpoints) to resize it.
- **Right-click** a field to delete it.

### 5 — Edit Field Properties
With a field selected, the **Properties** panel at the bottom of the sidebar shows its name and default value. Edit either, then click **Apply**.

### 6 — Copy & Paste
Select a field and press `Ctrl+C` (or click **Copy Field** in the sidebar), then `Ctrl+V` to paste. Each paste offsets the copy by 10 pt so fields don't stack.

### 7 — Save
Click **Save Fillable PDF** in the toolbar. Choose a destination and the app writes a standard AcroForm PDF that opens in Acrobat, browsers, and any compliant viewer.

## Project Structure

```
FillablePDF/
├── main.py                  # Entry point
├── requirements.txt
├── models/
│   └── form_field.py        # FormField dataclass
├── core/
│   ├── pdf_processor.py     # PDF loading and page rendering (PyMuPDF)
│   ├── field_detector.py    # Auto-detection of blank form fields
│   └── pdf_builder.py       # Writes AcroForm widgets back to the document
├── ui/
│   ├── pdf_canvas.py        # Scrollable canvas with interactive overlays
│   ├── sidebar.py           # Mode buttons, field list, properties panel
│   └── app_window.py        # Main window and application state
└── tests/
    ├── conftest.py
    ├── test_form_field.py
    ├── test_pdf_processor.py
    ├── test_field_detector.py
    └── test_pdf_builder.py
```

## Running Tests

```bash
pytest tests/
```

61 tests cover the data model, PDF processing, field detection, and PDF building.

## Field Types

| Type | Description |
|---|---|
| Text Field | Single-line or multi-line text input |
| Checkbox | Boolean on/off tick box |
| Radio Button | Single-selection button (uses checkbox widget when placed standalone) |
| Dropdown | Combo-box with selectable options |

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+C` | Copy selected field |
| `Ctrl+V` | Paste copied field (offset by 10 pt) |
