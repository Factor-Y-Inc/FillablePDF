from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk
from PIL import Image, ImageTk

from models.form_field import FormField

# Color per field type (outline + label)
_TYPE_COLORS: dict[str, str] = {
    "text":     "#4A90D9",  # blue
    "checkbox": "#27AE60",  # green
    "radio":    "#E67E22",  # orange
    "dropdown": "#9B59B6",  # purple
}
_SELECTED_COLOR = "#E74C3C"   # red — selected field
_CANVAS_BG = "#6B6B6B"        # neutral grey background behind the page
_HANDLE_HALF = 5              # half-size of resize handle squares in canvas pixels
_MIN_FIELD_PX = 10            # minimum field dimension in canvas pixels


class PDFCanvas(ctk.CTkFrame):
    """Scrollable canvas that displays a PDF page image and interactive field overlays.

    Coordinate convention
    ---------------------
    PyMuPDF (fitz) uses a **top-left origin** coordinate system for all
    operations: get_text, get_drawings, Widget.rect.  Canvas pixels also
    use top-left origin.  The only transform between the two systems is
    a uniform scale factor ``zoom``:

        canvas_px  = fitz_pt * zoom
        fitz_pt    = canvas_px / zoom
    """

    def __init__(self, parent: ctk.CTkFrame, **kwargs):
        super().__init__(parent, **kwargs)

        self._zoom: float = 1.5
        self._page_w_pt: float = 595.0   # populated on display_page()
        self._page_h_pt: float = 842.0

        self._image_ref: ImageTk.PhotoImage | None = None   # prevent GC
        self._fields: list[FormField] = []
        self._selected_name: str | None = None
        self._mode: str = "select"

        # Drag state for rubber-band rectangle (add-field modes)
        self._drag_start: tuple[float, float] | None = None
        self._drag_rect_id: int | None = None

        # Drag state for select-mode move / resize
        self._sel_drag_mode: str | None = None          # "move" | "resize_nw" | ...
        self._sel_drag_field: str | None = None         # name of field being dragged
        self._sel_drag_start: tuple[float, float] | None = None
        self._sel_drag_orig_rect: tuple[float, float, float, float] | None = None  # canvas coords
        self._sel_drag_preview_id: int | None = None

        # --- Callbacks (set by AppWindow) ---
        # on_field_placed(field_type, x0, y0, x1, y1)  — coords in fitz points
        self.on_field_placed: Callable[[str, float, float, float, float], None] | None = None
        # on_field_selected(name)
        self.on_field_selected: Callable[[str], None] | None = None
        # on_field_deleted(name)
        self.on_field_deleted: Callable[[str], None] | None = None
        # on_field_resized(name, x0, y0, x1, y1) — new rect in fitz points
        self.on_field_resized: Callable[[str, float, float, float, float], None] | None = None

        self._build_layout()
        self._bind_events()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            self,
            bg=_CANVAS_BG,
            highlightthickness=0,
            cursor="arrow",
        )
        self._vsb = tk.Scrollbar(self, orient="vertical",   command=self._canvas.yview)
        self._hsb = tk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)

        self._canvas.configure(
            yscrollcommand=self._vsb.set,
            xscrollcommand=self._hsb.set,
        )

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Switch interaction mode.  mode ∈ {"select","add_text","add_checkbox","add_radio","add_dropdown"}"""
        self._mode = mode
        cursor = "arrow" if mode == "select" else "crosshair"
        self._canvas.config(cursor=cursor)

    def display_page(
        self,
        pil_image: Image.Image,
        page_w_pt: float,
        page_h_pt: float,
        zoom: float,
    ) -> None:
        """Render *pil_image* on the canvas and update internal page dimensions."""
        self._zoom = zoom
        self._page_w_pt = page_w_pt
        self._page_h_pt = page_h_pt

        tk_image = ImageTk.PhotoImage(pil_image)
        self._image_ref = tk_image          # keep reference — Tk won't hold it

        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=tk_image, tags=("page_image",))
        self._canvas.config(
            scrollregion=(0, 0, pil_image.width, pil_image.height)
        )

    def draw_fields(
        self,
        fields: list[FormField],
        selected_name: str | None = None,
    ) -> None:
        """Redraw all field overlay rectangles on top of the page image."""
        self._fields = fields
        self._selected_name = selected_name

        self._canvas.delete("field_overlay")

        for field in fields:
            cx0, cy0, cx1, cy1 = self._fitz_to_canvas(
                field.x0, field.y0, field.x1, field.y1
            )
            is_selected = field.name == selected_name
            color = _SELECTED_COLOR if is_selected else _TYPE_COLORS.get(field.field_type, "#888888")

            self._canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=color,
                width=2 if not is_selected else 3,
                fill="",
                tags=("field_overlay", f"field:{field.name}"),
            )
            # Small name label at top-left of the box
            self._canvas.create_text(
                cx0 + 3, cy0 + 2,
                text=field.name,
                anchor="nw",
                fill=color,
                font=("Helvetica", 8),
                tags=("field_overlay", f"field_label:{field.name}"),
            )

            # Draw 8 resize handles for the selected field
            if is_selected:
                for hx, hy in self._get_handle_centers(cx0, cy0, cx1, cy1).values():
                    self._canvas.create_rectangle(
                        hx - _HANDLE_HALF, hy - _HANDLE_HALF,
                        hx + _HANDLE_HALF, hy + _HANDLE_HALF,
                        fill=_SELECTED_COLOR,
                        outline="white",
                        width=1,
                        tags=("field_overlay",),
                    )

    # ------------------------------------------------------------------
    # Event binding
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self._canvas.bind("<Button-1>",        self._on_mouse_press)
        self._canvas.bind("<B1-Motion>",       self._on_mouse_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._canvas.bind("<Button-3>",        self._on_right_click)
        # Mouse-wheel scrolling (Windows)
        self._canvas.bind("<MouseWheel>",       self._on_mousewheel_y)
        self._canvas.bind("<Shift-MouseWheel>", self._on_mousewheel_x)

    def _on_mousewheel_y(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_x(self, event: tk.Event) -> None:
        self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Mouse interactions
    # ------------------------------------------------------------------

    def _on_mouse_press(self, event: tk.Event) -> None:
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)

        if self._mode == "select":
            # 1. Check resize handles on the currently selected field first
            if self._selected_name is not None:
                sel_field = next((f for f in self._fields if f.name == self._selected_name), None)
                if sel_field is not None:
                    rc = self._fitz_to_canvas(sel_field.x0, sel_field.y0, sel_field.x1, sel_field.y1)
                    handle = self._hit_handle(cx, cy, *rc)
                    if handle is not None:
                        self._sel_drag_mode = f"resize_{handle}"
                        self._sel_drag_field = self._selected_name
                        self._sel_drag_start = (cx, cy)
                        self._sel_drag_orig_rect = rc
                        return

            # 2. Check if click is inside any field body → move or select
            name = self._field_at(cx, cy)
            if name is not None:
                if name == self._selected_name:
                    # Start a move drag on already-selected field
                    sel_field = next((f for f in self._fields if f.name == name), None)
                    if sel_field is not None:
                        rc = self._fitz_to_canvas(sel_field.x0, sel_field.y0, sel_field.x1, sel_field.y1)
                        self._sel_drag_mode = "move"
                        self._sel_drag_field = name
                        self._sel_drag_start = (cx, cy)
                        self._sel_drag_orig_rect = rc
                        return
                # Select a different field
                if self.on_field_selected:
                    self.on_field_selected(name)
            return

        # Add-field modes: start drag
        self._drag_start = (cx, cy)
        if self._drag_rect_id is not None:
            self._canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None

    def _on_mouse_drag(self, event: tk.Event) -> None:
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)

        # Select-mode: move or resize drag
        if self._mode == "select":
            if self._sel_drag_mode is None or self._sel_drag_orig_rect is None:
                return
            new_rect = self._compute_drag_rect(cx, cy)
            if new_rect is None:
                return
            # Draw live dashed preview
            if self._sel_drag_preview_id is not None:
                self._canvas.delete(self._sel_drag_preview_id)
            r = new_rect
            self._sel_drag_preview_id = self._canvas.create_rectangle(
                r[0], r[1], r[2], r[3],
                outline=_SELECTED_COLOR,
                width=2,
                dash=(5, 3),
                tags=("drag_preview",),
            )
            return

        # Add-field modes: rubber-band
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start
        if self._drag_rect_id is not None:
            self._canvas.delete(self._drag_rect_id)
        field_type = self._mode.replace("add_", "")
        color = _TYPE_COLORS.get(field_type, "#888888")
        self._drag_rect_id = self._canvas.create_rectangle(
            x0, y0, cx, cy,
            outline=color,
            width=2,
            dash=(5, 3),
            tags=("drag_rect",),
        )

    def _on_mouse_release(self, event: tk.Event) -> None:
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)

        # Select-mode: finish move or resize
        if self._mode == "select":
            if self._sel_drag_mode is not None:
                if self._sel_drag_preview_id is not None:
                    self._canvas.delete(self._sel_drag_preview_id)
                    self._sel_drag_preview_id = None
                new_rect = self._compute_drag_rect(cx, cy)
                name = self._sel_drag_field
                # Reset drag state before emitting callback
                self._sel_drag_mode = None
                self._sel_drag_field = None
                self._sel_drag_start = None
                self._sel_drag_orig_rect = None
                if new_rect is not None and name is not None and self.on_field_resized:
                    px0, py0, px1, py1 = self._canvas_to_fitz(*new_rect)
                    self.on_field_resized(name, px0, py0, px1, py1)
            return

        # Add-field modes: finish rubber-band
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start

        if self._drag_rect_id is not None:
            self._canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None
        self._drag_start = None

        # Ignore drags that are too small (accidental clicks)
        if abs(cx - x0) < 5 or abs(cy - y0) < 5:
            return

        # Normalize so x0 < x1, y0 < y1
        cx0, cx1 = (min(x0, cx), max(x0, cx))
        cy0, cy1 = (min(y0, cy), max(y0, cy))

        px0, py0, px1, py1 = self._canvas_to_fitz(cx0, cy0, cx1, cy1)
        field_type = self._mode.replace("add_", "")

        if self.on_field_placed:
            self.on_field_placed(field_type, px0, py0, px1, py1)

    def _on_right_click(self, event: tk.Event) -> None:
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        name = self._field_at(cx, cy)
        if name is None:
            return

        menu = tk.Menu(self._canvas, tearoff=0)
        menu.add_command(
            label=f"Delete \"{name}\"",
            command=lambda n=name: self._emit_delete(n),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _emit_delete(self, name: str) -> None:
        if self.on_field_deleted:
            self.on_field_deleted(name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _field_at(self, cx: float, cy: float) -> str | None:
        """Return name of the topmost field whose canvas rect contains (cx, cy)."""
        for field in reversed(self._fields):
            fx0, fy0, fx1, fy1 = self._fitz_to_canvas(
                field.x0, field.y0, field.x1, field.y1
            )
            if fx0 <= cx <= fx1 and fy0 <= cy <= fy1:
                return field.name
        return None

    def _fitz_to_canvas(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> tuple[float, float, float, float]:
        """Scale fitz (top-left origin, points) → canvas pixels."""
        z = self._zoom
        return x0 * z, y0 * z, x1 * z, y1 * z

    def _canvas_to_fitz(
        self, cx0: float, cy0: float, cx1: float, cy1: float
    ) -> tuple[float, float, float, float]:
        """Scale canvas pixels → fitz (top-left origin, points)."""
        z = self._zoom
        return cx0 / z, cy0 / z, cx1 / z, cy1 / z

    def _get_handle_centers(
        self, cx0: float, cy0: float, cx1: float, cy1: float
    ) -> dict[str, tuple[float, float]]:
        """Return a dict of handle name → (center_x, center_y) in canvas pixels."""
        mx = (cx0 + cx1) / 2
        my = (cy0 + cy1) / 2
        return {
            "nw": (cx0, cy0), "n": (mx, cy0), "ne": (cx1, cy0),
            "e":  (cx1, my),
            "se": (cx1, cy1), "s": (mx, cy1), "sw": (cx0, cy1),
            "w":  (cx0, my),
        }

    def _hit_handle(
        self, cx: float, cy: float,
        rx0: float, ry0: float, rx1: float, ry1: float
    ) -> str | None:
        """Return the handle name under (cx, cy), or None."""
        for name, (hx, hy) in self._get_handle_centers(rx0, ry0, rx1, ry1).items():
            if abs(cx - hx) <= _HANDLE_HALF + 2 and abs(cy - hy) <= _HANDLE_HALF + 2:
                return name
        return None

    def _compute_drag_rect(
        self, cx: float, cy: float
    ) -> tuple[float, float, float, float] | None:
        """Compute the new canvas rect for the current drag at mouse position (cx, cy).
        Returns None if drag state is incomplete or result is below minimum size."""
        if self._sel_drag_start is None or self._sel_drag_orig_rect is None:
            return None
        sx, sy = self._sel_drag_start
        dx, dy = cx - sx, cy - sy
        x0, y0, x1, y1 = self._sel_drag_orig_rect
        mode = self._sel_drag_mode

        if mode == "move":
            x0, y0, x1, y1 = x0 + dx, y0 + dy, x1 + dx, y1 + dy
        elif mode == "resize_nw": x0 += dx; y0 += dy
        elif mode == "resize_n":  y0 += dy
        elif mode == "resize_ne": x1 += dx; y0 += dy
        elif mode == "resize_e":  x1 += dx
        elif mode == "resize_se": x1 += dx; y1 += dy
        elif mode == "resize_s":  y1 += dy
        elif mode == "resize_sw": x0 += dx; y1 += dy
        elif mode == "resize_w":  x0 += dx

        # Normalise so x0 < x1, y0 < y1 and enforce minimum size
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        if x1 - x0 < _MIN_FIELD_PX or y1 - y0 < _MIN_FIELD_PX:
            return None
        return (x0, y0, x1, y1)
