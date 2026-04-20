from __future__ import annotations

import copy
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.pdf_processor import PDFProcessor
from core.field_detector import FieldDetector
from core.pdf_builder import PDFBuilder
from models.form_field import FormField
from ui.pdf_canvas import PDFCanvas
from ui.sidebar import Sidebar

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

_ZOOM = 1.5

_MODE_HINTS: dict[str, str] = {
    "select":       "Mode: Select — click to select, drag to move/resize, Ctrl+C copy, Ctrl+V paste",
    "add_text":     "Mode: Text Field — click and drag to place a text field",
    "add_checkbox": "Mode: Checkbox — click and drag to place a checkbox",
    "add_radio":    "Mode: Radio Button — click and drag to place a radio button",
    "add_dropdown": "Mode: Dropdown — click and drag to place a dropdown",
}


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Fillable PDF Creator")
        self.geometry("1100x780")
        self.minsize(800, 600)

        self._processor = PDFProcessor()
        self._detector = FieldDetector()

        # fields_by_page: page_num → list[FormField]
        self._fields_by_page: dict[int, list[FormField]] = {}
        self._current_page: int = 0
        self._selected_name: str | None = None
        self._field_counter: int = 0   # global counter for unique default names
        self._clipboard: FormField | None = None  # copy/paste buffer

        self._build_layout()
        self._wire_callbacks()
        self._bind_keys()
        self._update_toolbar_state()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Toolbar ───────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, height=50, corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_columnconfigure(5, weight=1)  # spacer
        toolbar.grid_columnconfigure(6, weight=0)

        self._btn_open = ctk.CTkButton(
            toolbar, text="Open PDF", width=110, command=self._open_pdf
        )
        self._btn_open.grid(row=0, column=0, padx=(10, 4), pady=8)

        self._btn_detect = ctk.CTkButton(
            toolbar, text="Auto-Detect Fields", width=150,
            state="disabled", command=self._run_auto_detect
        )
        self._btn_detect.grid(row=0, column=1, padx=4, pady=8)

        self._btn_save = ctk.CTkButton(
            toolbar, text="Save Fillable PDF", width=150,
            state="disabled", command=self._save_pdf
        )
        self._btn_save.grid(row=0, column=2, padx=4, pady=8)

        # Page navigation
        nav_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        nav_frame.grid(row=0, column=3, padx=(20, 4), pady=8)

        self._btn_prev = ctk.CTkButton(
            nav_frame, text="◀", width=32, state="disabled",
            command=self._prev_page
        )
        self._btn_prev.grid(row=0, column=0, padx=2)

        self._lbl_page = ctk.CTkLabel(nav_frame, text="—", width=80, anchor="center")
        self._lbl_page.grid(row=0, column=1, padx=4)

        self._btn_next = ctk.CTkButton(
            nav_frame, text="▶", width=32, state="disabled",
            command=self._next_page
        )
        self._btn_next.grid(row=0, column=2, padx=2)

        self._btn_help = ctk.CTkButton(
            toolbar, text="About", width=70,
            command=self._open_readme,
        )
        self._btn_help.grid(row=0, column=6, padx=(4, 10), pady=8)

        # ── Main area ─────────────────────────────────────────────────
        self._canvas = PDFCanvas(self)
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        self._sidebar = Sidebar(self)
        self._sidebar.grid(row=1, column=1, sticky="ns", padx=(0, 0), pady=0)

        # ── Status bar ────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Open a PDF to get started.")
        status_bar = ctk.CTkLabel(
            self, textvariable=self._status_var,
            anchor="w", height=24,
            fg_color=("gray85", "gray20"),
            corner_radius=0,
        )
        status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

    # ------------------------------------------------------------------
    # Callback wiring
    # ------------------------------------------------------------------

    def _wire_callbacks(self) -> None:
        # Canvas → AppWindow
        self._canvas.on_field_placed   = self._on_field_placed
        self._canvas.on_field_selected = self._on_field_selected
        self._canvas.on_field_deleted  = self._on_field_deleted
        self._canvas.on_field_resized  = self._on_field_resized

        # Sidebar → AppWindow
        self._sidebar.on_mode_changed   = self._on_mode_changed
        self._sidebar.on_field_deleted  = self._on_field_deleted
        self._sidebar.on_field_updated  = self._on_field_updated
        self._sidebar.on_field_copy     = self._copy_selected_field

    def _bind_keys(self) -> None:
        self.bind("<Control-c>", lambda e: self._copy_selected_field())
        self.bind("<Control-v>", lambda e: self._paste_field())

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------

    def _open_readme(self) -> None:
        webbrowser.open("https://github.com/Factor-Y-Inc/FillablePDF#readme")

    def _open_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._processor.load(path)
        except Exception as exc:
            messagebox.showerror("Error opening PDF", str(exc))
            return

        self._fields_by_page = {}
        self._current_page = 0
        self._selected_name = None
        self._field_counter = 0

        self._update_toolbar_state()
        self._render_current_page()
        self._status("PDF loaded — use Auto-Detect or drag to place fields.")

    def _run_auto_detect(self) -> None:
        if not self._processor.is_loaded:
            return
        page = self._processor.get_raw_page(self._current_page)
        detected = self._detector.detect(page)

        if not detected:
            self._status("Auto-detect found no blank fields on this page.")
            return

        existing = self._fields_by_page.get(self._current_page, [])
        existing_names = {f.name for f in existing}

        added = 0
        for f in detected:
            # Assign a unique name that doesn't clash with manual fields
            self._field_counter += 1
            f.name = f"field_{self._field_counter}"
            while f.name in existing_names:
                self._field_counter += 1
                f.name = f"field_{self._field_counter}"
            existing_names.add(f.name)
            existing.append(f)
            added += 1

        self._fields_by_page[self._current_page] = existing
        self._refresh_view()
        self._status(f"Auto-detect added {added} field(s) on page {self._current_page + 1}.")

    def _save_pdf(self) -> None:
        if not self._processor.is_loaded:
            return
        out_path = filedialog.asksaveasfilename(
            title="Save Fillable PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return

        all_fields = [f for page_fields in self._fields_by_page.values() for f in page_fields]
        if not all_fields:
            messagebox.showinfo("Nothing to save", "No fields have been placed yet.")
            return

        try:
            doc = self._processor.get_document()
            builder = PDFBuilder(doc)
            builder.apply_fields(all_fields)
            builder.save(out_path)
        except Exception as exc:
            messagebox.showerror("Error saving PDF", str(exc))
            return

        self._status(f"Saved: {out_path}")
        messagebox.showinfo("Saved", f"Fillable PDF saved to:\n{out_path}")

    # ------------------------------------------------------------------
    # Page navigation
    # ------------------------------------------------------------------

    def _prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._selected_name = None
            self._render_current_page()

    def _next_page(self) -> None:
        if self._processor.is_loaded and self._current_page < self._processor.page_count - 1:
            self._current_page += 1
            self._selected_name = None
            self._render_current_page()

    # ------------------------------------------------------------------
    # Canvas callbacks
    # ------------------------------------------------------------------

    def _on_field_placed(
        self, field_type: str, x0: float, y0: float, x1: float, y1: float
    ) -> None:
        self._field_counter += 1
        name = f"field_{self._field_counter}"
        try:
            field = FormField(
                field_type=field_type,
                x0=x0, y0=y0, x1=x1, y1=y1,
                name=name,
                page_num=self._current_page,
            )
        except ValueError:
            return  # rect too small — silently ignore

        page_fields = self._fields_by_page.setdefault(self._current_page, [])
        page_fields.append(field)
        self._selected_name = name
        self._refresh_view()
        self._status(f"Added {field_type} field '{name}' on page {self._current_page + 1}.")

    def _on_field_selected(self, name: str) -> None:
        self._selected_name = name
        self._refresh_view(redraw_canvas=False)
        self._canvas.draw_fields(
            self._fields_by_page.get(self._current_page, []),
            selected_name=name,
        )
        self._status(f"Selected: {name}")

    def _on_field_deleted(self, name: str) -> None:
        page_fields = self._fields_by_page.get(self._current_page, [])
        self._fields_by_page[self._current_page] = [f for f in page_fields if f.name != name]
        if self._selected_name == name:
            self._selected_name = None
        self._refresh_view()
        self._status(f"Deleted field '{name}'.")

    def _on_field_resized(
        self, name: str, x0: float, y0: float, x1: float, y1: float
    ) -> None:
        """Update the stored rect for a field after a move or resize drag."""
        page_fields = self._fields_by_page.get(self._current_page, [])
        for f in page_fields:
            if f.name == name:
                f.x0, f.y0, f.x1, f.y1 = x0, y0, x1, y1
                break
        self._refresh_view()
        self._status(f"Field '{name}' updated.")

    # ------------------------------------------------------------------
    # Copy / Paste
    # ------------------------------------------------------------------

    def _copy_selected_field(self) -> None:
        """Copy the currently selected field to the clipboard."""
        if self._selected_name is None:
            return
        page_fields = self._fields_by_page.get(self._current_page, [])
        src = next((f for f in page_fields if f.name == self._selected_name), None)
        if src is None:
            return
        self._clipboard = copy.copy(src)
        self._status(f"Copied '{src.name}' — press Ctrl+V to paste.")

    def _paste_field(self) -> None:
        """Paste the clipboard field as a new field, offset by 10pt."""
        if self._clipboard is None:
            return
        if not self._processor.is_loaded:
            return

        _OFFSET = 10.0  # fitz points
        w_pt, h_pt = self._processor.page_size_pt(self._current_page)

        x0 = min(self._clipboard.x0 + _OFFSET, w_pt - (self._clipboard.x1 - self._clipboard.x0))
        y0 = min(self._clipboard.y0 + _OFFSET, h_pt - (self._clipboard.y1 - self._clipboard.y0))
        x1 = x0 + (self._clipboard.x1 - self._clipboard.x0)
        y1 = y0 + (self._clipboard.y1 - self._clipboard.y0)

        self._field_counter += 1
        name = f"field_{self._field_counter}"
        existing_names = {f.name for f in self._fields_by_page.get(self._current_page, [])}
        while name in existing_names:
            self._field_counter += 1
            name = f"field_{self._field_counter}"

        try:
            new_field = FormField(
                field_type=self._clipboard.field_type,
                x0=x0, y0=y0, x1=x1, y1=y1,
                name=name,
                page_num=self._current_page,
                default_value=self._clipboard.default_value,
                label=self._clipboard.label,
            )
        except ValueError:
            return

        page_fields = self._fields_by_page.setdefault(self._current_page, [])
        page_fields.append(new_field)
        self._selected_name = name
        # Advance clipboard offset so repeated pastes don't stack on same spot
        self._clipboard = copy.copy(new_field)
        self._refresh_view()
        self._status(f"Pasted '{name}' on page {self._current_page + 1}.")

    # ------------------------------------------------------------------
    # Sidebar callbacks
    # ------------------------------------------------------------------

    def _on_mode_changed(self, mode: str) -> None:
        self._canvas.set_mode(mode)
        self._status(_MODE_HINTS.get(mode, ""))

    def _on_field_updated(self, old_name: str, new_name: str, default_val: str) -> None:
        page_fields = self._fields_by_page.get(self._current_page, [])
        # Reject duplicate names (other than the field itself)
        existing_names = {f.name for f in page_fields if f.name != old_name}
        if new_name in existing_names:
            messagebox.showwarning(
                "Duplicate name",
                f"A field named '{new_name}' already exists on this page.",
            )
            return
        for f in page_fields:
            if f.name == old_name:
                f.name = new_name
                f.default_value = default_val
                break
        if self._selected_name == old_name:
            self._selected_name = new_name
        self._refresh_view()
        self._status(f"Field renamed to '{new_name}'.")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_current_page(self) -> None:
        pil_image = self._processor.render_page(self._current_page, zoom=_ZOOM)
        w_pt, h_pt = self._processor.page_size_pt(self._current_page)
        self._canvas.display_page(pil_image, w_pt, h_pt, zoom=_ZOOM)
        self._refresh_view()
        total = self._processor.page_count
        self._lbl_page.configure(text=f"Page {self._current_page + 1} / {total}")
        self._btn_prev.configure(state="normal" if self._current_page > 0 else "disabled")
        self._btn_next.configure(state="normal" if self._current_page < total - 1 else "disabled")

    def _refresh_view(self, redraw_canvas: bool = True) -> None:
        fields = self._fields_by_page.get(self._current_page, [])
        if redraw_canvas:
            self._canvas.draw_fields(fields, selected_name=self._selected_name)
        self._sidebar.refresh_fields(fields, selected_name=self._selected_name)

    def _update_toolbar_state(self) -> None:
        loaded = self._processor.is_loaded
        state = "normal" if loaded else "disabled"
        self._btn_detect.configure(state=state)
        self._btn_save.configure(state=state)

    def _status(self, msg: str) -> None:
        self._status_var.set(f"  {msg}")
