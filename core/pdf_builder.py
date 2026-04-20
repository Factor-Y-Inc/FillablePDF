from __future__ import annotations

from collections import defaultdict

import fitz  # PyMuPDF
from models.form_field import FormField

# Map our internal field_type strings to fitz widget-type constants.
_WIDGET_TYPE_MAP: dict[str, int] = {
    "text": fitz.PDF_WIDGET_TYPE_TEXT,
    "checkbox": fitz.PDF_WIDGET_TYPE_CHECKBOX,
    "radio": fitz.PDF_WIDGET_TYPE_RADIOBUTTON,
    "dropdown": fitz.PDF_WIDGET_TYPE_COMBOBOX,
}


class PDFBuilder:
    """Applies FormField objects to a fitz.Document as AcroForm widgets and saves."""

    def __init__(self, doc: fitz.Document):
        self._doc = doc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_fields(self, fields: list[FormField]) -> None:
        """Add all FormField objects to the document as AcroForm widgets.

        Fields are grouped by page_num and processed page-by-page.
        Any existing widget with the same field name is removed first to
        avoid duplicate entries.
        """
        by_page: dict[int, list[FormField]] = defaultdict(list)
        for f in fields:
            by_page[f.page_num].append(f)

        for page_num, page_fields in by_page.items():
            if page_num < 0 or page_num >= self._doc.page_count:
                continue
            page = self._doc[page_num]
            self._remove_existing_widgets(page, {f.name for f in page_fields})
            for field in page_fields:
                self._add_widget(page, field)

    def save(self, output_path: str) -> None:
        """Save the modified document to *output_path*.

        Uses incremental=False to produce a clean, self-contained file that
        renders correctly in all PDF viewers.
        """
        self._doc.save(output_path, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_widget(self, page: fitz.Page, field: FormField) -> None:
        widget_type = _WIDGET_TYPE_MAP.get(field.field_type)
        if widget_type is None:
            raise ValueError(f"Unsupported field_type: {field.field_type!r}")

        widget = fitz.Widget()
        widget.field_type = widget_type
        widget.field_name = field.name
        widget.field_value = field.default_value

        # fitz.Rect uses PDF coord system (bottom-left origin) — matches our stored rect.
        widget.rect = fitz.Rect(field.x0, field.y0, field.x1, field.y1)

        # Visual styling
        widget.border_color = (0, 0, 0)       # black border
        widget.border_width = 0.5
        widget.fill_color = (1, 1, 1)          # white background
        widget.text_color = (0, 0, 0)          # black text

        if field.field_type == "text":
            widget.text_fontsize = 10
            widget.text_font = "Helv"
            widget.field_flags = 0             # no special flags (multiline off by default)

        elif field.field_type == "checkbox":
            widget.field_value = "Off"
            widget.field_flags = 0

        elif field.field_type == "radio":
            # PDF radio buttons require a parent group (AcroForm constraint).
            # Standalone radio buttons are created as checkboxes; the circular
            # appearance distinguishes them visually for the end user.
            widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
            widget.field_value = "Off"
            widget.field_flags = 0

        elif field.field_type == "dropdown":
            # Empty choice list — caller can extend via widget.choice_values
            widget.choice_values = []
            widget.field_flags = fitz.PDF_CH_FIELD_IS_COMBO

        page.add_widget(widget)

    def _remove_existing_widgets(
        self, page: fitz.Page, names: set[str]
    ) -> None:
        """Delete any existing widgets on *page* whose field names are in *names*."""
        for widget in page.widgets():
            if widget.field_name in names:
                page.delete_widget(widget)
