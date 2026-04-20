from dataclasses import dataclass, field
from typing import Optional

# Supported field types
FIELD_TYPES = ("text", "checkbox", "radio", "dropdown")


@dataclass
class FormField:
    """Represents a single form field to be added to a PDF page."""

    field_type: str          # "text" | "checkbox" | "radio" | "dropdown"
    # PDF coordinate rect as (x0, y0, x1, y1) in bottom-left origin points
    x0: float
    y0: float
    x1: float
    y1: float
    name: str
    page_num: int
    default_value: str = ""
    # Optional display label (used by auto-detector to describe the field)
    label: str = ""

    def pdf_rect_tuple(self) -> tuple:
        """Return (x0, y0, x1, y1) suitable for fitz.Rect(*field.pdf_rect_tuple())."""
        return (self.x0, self.y0, self.x1, self.y1)

    def __post_init__(self):
        if self.field_type not in FIELD_TYPES:
            raise ValueError(
                f"field_type must be one of {FIELD_TYPES}, got {self.field_type!r}"
            )
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError(
                f"Invalid rect: ({self.x0}, {self.y0}, {self.x1}, {self.y1}) — "
                "x1 must be > x0 and y1 must be > y0"
            )
