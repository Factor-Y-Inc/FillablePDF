# Plan: Fillable PDF GUI App (Python Desktop)

## Overview
Desktop Python app where user opens a PDF, sees an interactive preview, auto-detects blank form areas (underscores, empty boxes), manually places additional fields by click-and-drag, then saves a standard fillable PDF.

**Stack**: customtkinter (shell UI) + tkinter Canvas (PDF preview/overlay) + PyMuPDF (rendering, detection, widget creation) + Pillow (image bridge)

---

## Project Structure
```
FillablePDF/
├── main.py
├── requirements.txt
├── ui/
│   ├── __init__.py
│   ├── app_window.py       # Main CTk window, toolbar, page nav, layout
│   ├── pdf_canvas.py       # Scrollable Canvas: renders page image, draws field overlays, handles mouse
│   └── sidebar.py          # Field type buttons, fields list, properties panel
├── core/
│   ├── __init__.py
│   ├── pdf_processor.py    # Load PDF, render page to PIL Image via PyMuPDF
│   ├── field_detector.py   # Auto-detect: underscores, drawings, whitespace heuristics
│   └── pdf_builder.py      # Add fitz.Widget objects to page and save
└── models/
    ├── __init__.py
    └── form_field.py       # FormField dataclass: type, rect (PDF coords), name, page_num, default_value
```

---

## Phases

### Phase 1 – Project Scaffold
1. Create `requirements.txt`: PyMuPDF, customtkinter, Pillow
2. Create package `__init__.py` files
3. Create `FormField` dataclass in `models/form_field.py`
   - Fields: `field_type` (str: "text"|"checkbox"|"radio"|"dropdown"), `pdf_rect` (fitz.Rect), `name` (str), `page_num` (int), `default_value` (str)

### Phase 2 – PDF Backend (core/)
4. `pdf_processor.py`
   - `PDFProcessor.load(path)` → opens with `fitz.open()`
   - `render_page(page_num, zoom=1.5)` → returns PIL Image via `page.get_pixmap(matrix=fitz.Matrix(zoom,zoom))` → `Image.frombytes()`
   - Exposes `page_count`, `page_rect(page_num)` for coord mapping
5. `field_detector.py`
   - `FieldDetector.detect(page)` → returns list of `FormField` (type="text")
   - Strategy: `page.get_text("rawdict")` → find spans of underscores (≥3 chars of `_`)
   - `page.get_drawings()` → find horizontal line segments (width > 30pt, very thin height) and empty rectangles
   - Return detected fields with inferred names ("field_1", "field_2" …)
6. `pdf_builder.py`
   - `PDFBuilder.apply_fields(doc, fields_by_page)` → iterates pages, creates `fitz.Widget` per field, calls `page.add_widget(w)`
   - Field type mapping: "text" → `fitz.PDF_WIDGET_TYPE_TEXT`, "checkbox" → `fitz.PDF_WIDGET_TYPE_CHECKBOX`, etc.
   - `save(output_path)` → `doc.save(output_path)`
   - **Coordinate note**: `pdf_rect` is already in PDF coords (bottom-left origin); no transform needed

### Phase 3 – Canvas Widget (ui/pdf_canvas.py)
7. `PDFCanvas` class wrapping `tk.Canvas` inside a `CTkFrame` with scrollbars
   - `display_page(pil_image)` → convert to `ImageTk.PhotoImage`, `canvas.create_image(0,0,...)`; keep reference to prevent GC
   - `draw_fields(fields, selected_name)` → for each FormField, convert PDF rect → canvas rect (scale by zoom, flip Y: `canvas_y = (page_h - pdf_y) * zoom`); draw colored rectangle + label text; color-coded by type
   - **Mouse interaction modes**: "select", "add_text", "add_checkbox", "add_radio", "add_dropdown"
   - Drag start on `<Button-1>` → drag rubber-band rect → on `<ButtonRelease-1>` emit `on_field_placed(canvas_rect)` callback
   - Click on existing field rect → `on_field_selected(name)` callback
   - Right-click on existing field → context menu "Delete"
8. Coordinate helpers: `canvas_to_pdf_rect(x1,y1,x2,y2, zoom, page_h)` and reverse

### Phase 4 – Sidebar (ui/sidebar.py)
9. `Sidebar` CTkFrame with:
   - Field type radio buttons / toggle buttons (Text, Checkbox, Radio Button, Dropdown)
   - Scrollable field list (CTkScrollableFrame): one row per FormField with name label and delete button
   - Properties panel (below list): Name entry, Default Value entry, "Apply" button
   - Emits callbacks: `on_mode_changed(mode)`, `on_field_deleted(name)`, `on_field_updated(name, new_name, default_val)`

### Phase 5 – Main Window (ui/app_window.py)
10. `AppWindow(CTk)`:
    - Toolbar row: "Open PDF" button, "Auto-Detect Fields" button, "Save Fillable PDF" button, page nav (`< Page N/M >`)
    - Layout: PDFCanvas (center, expandable) + Sidebar (right, fixed width ~220px)
    - `open_pdf()` → `filedialog.askopenfilename()` → `PDFProcessor.load()` → render page 0 → `PDFCanvas.display_page()`
    - `run_auto_detect()` → `FieldDetector.detect(page)` → append to field list → redraw canvas
    - `save_pdf()` → `filedialog.asksaveasfilename()` → `PDFBuilder.apply_fields()` → `save()`
    - Wires all callbacks between canvas and sidebar
    - Status bar at bottom showing current mode hint

### Phase 6 – Entry Point
11. `main.py`: Instantiate `AppWindow`, call `mainloop()`

---

## Coordinate Transform Reference
- PDF origin: bottom-left. Canvas origin: top-left.
- canvas_x = pdf_x * zoom
- canvas_y = (page_height_pt - pdf_y) * zoom   ← flip Y
- Reverse: pdf_x = canvas_x / zoom; pdf_y = page_height_pt - canvas_y / zoom

## Key Implementation Notes
- Keep PIL `ImageTk.PhotoImage` reference in instance variable (not local var) to prevent GC
- `page.add_widget()` modifies the page in-place; call `doc.save(new_path, incremental=False)`
- Auto-detected underscore fields: search for `text span` where `span["text"].strip("_") == ""` and `len(span["text"]) >= 4`
- For drawings detection: `path["rect"]` exists for rectangle paths; check `path["fill"] is None` and small height for lines

## Dependencies
- PyMuPDF >= 1.23
- customtkinter >= 5.2
- Pillow >= 10.0

## Verification Steps
1. `pip install -r requirements.txt` completes without errors
2. Open a sample non-fillable PDF → page renders visibly in the canvas
3. Click "Auto-Detect" → at least one yellow overlay appears on a PDF with underscores
4. Click-drag on canvas in "Text Field" mode → blue rectangle appears
5. Sidebar field list updates with new entry; rename via properties panel works
6. Save → open output in Adobe Reader/browser → form fields are present and fillable
7. Test with multi-page PDF → page navigation works, fields persist per page

# Plan: Build Standalone Windows EXE

## Context
- Project: FillablePDF (c:\Users\admin\Projects\FillablePDF)
- Entry point: main.py → ui/app_window.py → AppWindow (extends ctk.CTk)
- Dependencies: PyMuPDF (fitz), customtkinter, Pillow, tkinter (stdlib)
- No bundled assets/resources

## Tool: PyInstaller
Best choice for a GUI Python app on Windows. Bundles interpreter + all dependencies into dist\FillablePDF\.

## Key Challenges
1. **customtkinter** ships theme JSON + image assets — PyInstaller won't auto-collect them. Must use `--collect-data customtkinter` or `collect_data_files('customtkinter')` in spec.
2. **PyMuPDF/fitz** has native DLLs — needs `--collect-all fitz` to bundle correctly.
3. **PIL._tkinter_finder** is a hidden import needed for Pillow+tkinter integration.
4. GUI app → use `--windowed` (no console window).

## Files to Create
- FillablePDF.spec (PyInstaller spec with collect_data_files for customtkinter + collect_all for fitz)
- build.bat (convenience script)
- Update .gitignore to exclude dist/ and build/

## Steps
1. Install PyInstaller into the venv
2. Create FillablePDF.spec
3. Create build.bat
4. Update .gitignore
5. Run build, test output

## Verification
- Run dist\FillablePDF\FillablePDF.exe on a machine without Python installed
- Open a PDF, auto-detect fields, save fillable PDF
