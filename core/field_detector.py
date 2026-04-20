from __future__ import annotations

import fitz  # PyMuPDF
from models.form_field import FormField

# Minimum number of consecutive underscore characters to treat a text span
# as a blank field indicator.
_MIN_UNDERSCORE_RUN = 4

# Minimum width (points) for a horizontal line to be considered a blank field.
_MIN_LINE_WIDTH_PT = 30.0

# A line is "horizontal" when its height is at most this many points.
_MAX_LINE_HEIGHT_PT = 4.0

# Minimum area (points²) for an empty rectangle to be considered a field box.
_MIN_RECT_AREA_PT2 = 400.0

# Maximum area so we don't flag full-page border boxes as fields.
_MAX_RECT_AREA_PT2 = 50_000.0


class FieldDetector:
    """Scans a fitz.Page for likely blank form fields and returns FormField objects."""

    def detect(self, page: fitz.Page) -> list[FormField]:
        """Run all detection strategies and return a deduplicated list of FormFields."""
        fields: list[FormField] = []
        fields.extend(self._detect_underscores(page))
        fields.extend(self._detect_drawings(page))
        fields = self._deduplicate(fields)
        # Assign stable names after dedup
        for i, f in enumerate(fields, start=1):
            f.name = f"field_{i}"
        return fields

    # ------------------------------------------------------------------
    # Strategy 1: underscore-only text spans
    # ------------------------------------------------------------------

    def _detect_underscores(self, page: fitz.Page) -> list[FormField]:
        results: list[FormField] = []
        # Use "dict" format: spans have a "text" key (str).
        # "rawdict" in PyMuPDF ≥1.24 uses per-char dicts instead.
        data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in data.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text: str = span.get("text", "")
                    stripped = text.strip()
                    if len(stripped) >= _MIN_UNDERSCORE_RUN and set(stripped) <= {"_"}:
                        # fitz uses top-left origin for all coords — store as-is
                        x0, y0, x1, y1 = span["bbox"]
                        results.append(
                            FormField(
                                field_type="text",
                                x0=x0, y0=y0, x1=x1, y1=y1,
                                name="",  # assigned after dedup
                                page_num=page.number,
                                label=text.strip(),
                            )
                        )
        return results

    # ------------------------------------------------------------------
    # Strategy 2: drawings — horizontal lines and empty rectangles
    # ------------------------------------------------------------------

    def _detect_drawings(self, page: fitz.Page) -> list[FormField]:
        results: list[FormField] = []

        for path in page.get_drawings():
            rect = path.get("rect")
            if rect is None:
                continue

            width = rect.width
            height = rect.height

            # --- Horizontal line (thin, wide-enough) ---
            if height <= _MAX_LINE_HEIGHT_PT and width >= _MIN_LINE_WIDTH_PT:
                # Expand the thin line upward (in screen/fitz coords, smaller y = higher)
                # to create a 14pt-tall text field rect above the line.
                x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
                field_height = 14.0
                results.append(
                    FormField(
                        field_type="text",
                        x0=x0, y0=y0 - field_height, x1=x1, y1=y1,
                        name="",
                        page_num=page.number,
                        label="",
                    )
                )

            # --- Empty rectangle (possible text-box field) ---
            elif _MIN_RECT_AREA_PT2 <= (width * height) <= _MAX_RECT_AREA_PT2:
                fill = path.get("fill")
                fill_opacity = path.get("fill_opacity", 1.0)
                # Only flag unfilled or white-filled, non-opaque rectangles
                if fill is None or fill == (1, 1, 1) or fill_opacity == 0:
                    results.append(
                        FormField(
                            field_type="text",
                            x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1,
                            name="",
                            page_num=page.number,
                            label="",
                        )
                    )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _deduplicate(self, fields: list[FormField]) -> list[FormField]:
        """Remove fields whose centres are within 10 pt of each other (overlap)."""
        kept: list[FormField] = []
        for candidate in fields:
            cx = (candidate.x0 + candidate.x1) / 2
            cy = (candidate.y0 + candidate.y1) / 2
            too_close = False
            for existing in kept:
                ex = (existing.x0 + existing.x1) / 2
                ey = (existing.y0 + existing.y1) / 2
                if abs(cx - ex) < 10 and abs(cy - ey) < 10:
                    too_close = True
                    break
            if not too_close:
                kept.append(candidate)
        return kept
