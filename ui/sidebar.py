from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from models.form_field import FormField

# Maps internal mode strings to display labels, accent colors, and hover tints.
# Hover tints are light (light mode) / dark (dark mode) valid #RRGGBB values.
_FIELD_TYPES = [
    ("add_text",      "Text Field",   "#4A90D9", ("#C8DCF5", "#1A3A5C")),
    ("add_checkbox",  "Checkbox",     "#27AE60", ("#B8EDCF", "#0F4A29")),
    ("add_radio",     "Radio Button", "#E67E22", ("#FAD9B5", "#5C3009")),
    ("add_dropdown",  "Dropdown",     "#9B59B6", ("#DDBFED", "#3D1A5C")),
]


class Sidebar(ctk.CTkFrame):
    """Right-side panel: field-type buttons, scrollable field list, properties panel."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, width=240, **kwargs)
        self.grid_propagate(False)  # hold fixed width

        # --- Callbacks (set by AppWindow) ---
        self.on_mode_changed: Callable[[str], None] | None = None
        self.on_field_deleted: Callable[[str], None] | None = None
        self.on_field_updated: Callable[[str, str, str], None] | None = None  # old_name, new_name, default_val
        self.on_field_copy: Callable[[str], None] | None = None

        self._current_mode: str = "select"
        self._selected_name: str | None = None
        self._fields: list[FormField] = []
        self._mode_buttons: dict[str, ctk.CTkButton] = {}

        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # ── Section: Interaction mode ──────────────────────────────────
        ctk.CTkLabel(self, text="Add Field", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=10, pady=(12, 4), sticky="w"
        )

        # "Select" toggle button
        sel_btn = ctk.CTkButton(
            self,
            text="☛  Select / Move",
            height=30,
            anchor="w",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=lambda: self._set_mode("select"),
        )
        sel_btn.grid(row=1, column=0, padx=10, pady=2, sticky="ew")
        self._mode_buttons["select"] = sel_btn

        for i, (mode, label, color, hover) in enumerate(_FIELD_TYPES, start=2):
            btn = ctk.CTkButton(
                self,
                text=f"＋  {label}",
                height=30,
                anchor="w",
                fg_color="transparent",
                border_width=1,
                text_color=("gray10", "gray90"),
                hover_color=hover,
                command=lambda m=mode: self._set_mode(m),
            )
            btn.grid(row=i, column=0, padx=10, pady=2, sticky="ew")
            self._mode_buttons[mode] = btn

        # Highlight "select" as default active
        self._highlight_mode_button("select")

        # ── Separator ─────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color="gray50").grid(
            row=6, column=0, padx=10, pady=(10, 4), sticky="ew"
        )

        # ── Section: Field list ───────────────────────────────────────
        ctk.CTkLabel(self, text="Fields", font=ctk.CTkFont(weight="bold")).grid(
            row=7, column=0, padx=10, pady=(4, 4), sticky="w"
        )

        self._field_list_frame = ctk.CTkScrollableFrame(self, height=220)
        self._field_list_frame.grid(row=8, column=0, padx=10, pady=(0, 4), sticky="ew")
        self._field_list_frame.grid_columnconfigure(0, weight=1)

        # ── Separator ─────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color="gray50").grid(
            row=9, column=0, padx=10, pady=(4, 4), sticky="ew"
        )

        # ── Section: Properties ───────────────────────────────────────
        ctk.CTkLabel(self, text="Properties", font=ctk.CTkFont(weight="bold")).grid(
            row=10, column=0, padx=10, pady=(4, 4), sticky="w"
        )

        props = ctk.CTkFrame(self, fg_color="transparent")
        props.grid(row=11, column=0, padx=10, pady=(0, 4), sticky="ew")
        props.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(props, text="Name:").grid(row=0, column=0, padx=(0, 6), pady=3, sticky="w")
        self._name_var = tk.StringVar()
        self._name_entry = ctk.CTkEntry(props, textvariable=self._name_var, height=28)
        self._name_entry.grid(row=0, column=1, pady=3, sticky="ew")

        ctk.CTkLabel(props, text="Default:").grid(row=1, column=0, padx=(0, 6), pady=3, sticky="w")
        self._default_var = tk.StringVar()
        self._default_entry = ctk.CTkEntry(props, textvariable=self._default_var, height=28)
        self._default_entry.grid(row=1, column=1, pady=3, sticky="ew")

        self._apply_btn = ctk.CTkButton(
            self,
            text="Apply",
            height=30,
            state="disabled",
            command=self._on_apply,
        )
        self._apply_btn.grid(row=12, column=0, padx=10, pady=(4, 4), sticky="ew")

        self._copy_btn = ctk.CTkButton(
            self,
            text="Copy Field  (Ctrl+C)",
            height=30,
            state="disabled",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self._on_copy,
        )
        self._copy_btn.grid(row=13, column=0, padx=10, pady=(0, 12), sticky="ew")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_fields(self, fields: list[FormField], selected_name: str | None = None) -> None:
        """Rebuild the field list rows from *fields*."""
        self._fields = fields
        self._selected_name = selected_name

        # Clear existing rows
        for widget in self._field_list_frame.winfo_children():
            widget.destroy()

        for field in fields:
            self._add_field_row(field)

        # Populate properties panel for the selected field
        if selected_name is not None:
            match = next((f for f in fields if f.name == selected_name), None)
            if match:
                self._name_var.set(match.name)
                self._default_var.set(match.default_value)
                self._apply_btn.configure(state="normal")
                self._copy_btn.configure(state="normal")
            else:
                self._clear_properties()
        else:
            self._clear_properties()

    def select_field(self, name: str | None) -> None:
        """Highlight *name* in the list and populate the properties panel."""
        self._selected_name = name
        match = next((f for f in self._fields if f.name == name), None)
        if match:
            self._name_var.set(match.name)
            self._default_var.set(match.default_value)
            self._apply_btn.configure(state="normal")
            self._copy_btn.configure(state="normal")
        else:
            self._clear_properties()
        self.refresh_fields(self._fields, name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_field_row(self, field: FormField) -> None:
        row_frame = ctk.CTkFrame(
            self._field_list_frame,
            fg_color=("gray85", "gray25") if field.name == self._selected_name else "transparent",
            corner_radius=4,
        )
        row_frame.pack(fill="x", pady=1)
        row_frame.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(
            row_frame,
            text=f"[{field.field_type[:3].upper()}] {field.name}",
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        lbl.grid(row=0, column=0, padx=6, pady=2, sticky="w")
        lbl.bind("<Button-1>", lambda e, n=field.name: self._on_row_click(n))
        row_frame.bind("<Button-1>", lambda e, n=field.name: self._on_row_click(n))

        del_btn = ctk.CTkButton(
            row_frame,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            text_color=("gray30", "gray70"),
            hover_color=("#FFCCCC", "#7A2020"),
            command=lambda n=field.name: self._on_delete(n),
        )
        del_btn.grid(row=0, column=1, padx=4, pady=2)

    def _on_row_click(self, name: str) -> None:
        self._selected_name = name
        self.refresh_fields(self._fields, name)
        if self.on_field_deleted:
            pass  # selection handled via select_field callback chain in AppWindow
        # Directly populate properties
        match = next((f for f in self._fields if f.name == name), None)
        if match:
            self._name_var.set(match.name)
            self._default_var.set(match.default_value)
            self._apply_btn.configure(state="normal")
            self._copy_btn.configure(state="normal")

    def _on_delete(self, name: str) -> None:
        if self.on_field_deleted:
            self.on_field_deleted(name)

    def _on_copy(self) -> None:
        if self._selected_name is not None and self.on_field_copy:
            self.on_field_copy(self._selected_name)

    def _on_apply(self) -> None:
        if self._selected_name is None:
            return
        new_name = self._name_var.get().strip()
        default_val = self._default_var.get()
        if not new_name:
            return
        if self.on_field_updated:
            self.on_field_updated(self._selected_name, new_name, default_val)

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._highlight_mode_button(mode)
        if self.on_mode_changed:
            self.on_mode_changed(mode)

    def _highlight_mode_button(self, active_mode: str) -> None:
        for mode, btn in self._mode_buttons.items():
            if mode == active_mode:
                btn.configure(fg_color=("gray75", "gray35"), border_color=("gray50", "gray60"))
            else:
                btn.configure(fg_color="transparent", border_color=("gray70", "gray40"))

    def _clear_properties(self) -> None:
        self._name_var.set("")
        self._default_var.set("")
        self._apply_btn.configure(state="disabled")
        self._copy_btn.configure(state="disabled")
