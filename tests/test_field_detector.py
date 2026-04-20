"""Tests for core.field_detector.FieldDetector."""
import fitz
import pytest

from core.field_detector import FieldDetector, _MIN_UNDERSCORE_RUN
from models.form_field import FormField


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_page() -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    return doc, page


def _page_with_underscores(count: int = 8) -> tuple[fitz.Document, fitz.Page]:
    doc, page = _blank_page()
    underscores = "_" * count
    # Insert underscores as their own text run so they form a single span
    page.insert_text((72, 100), underscores, fontsize=12, color=(0, 0, 0))
    return doc, page


def _page_with_short_underscores(count: int = 2) -> tuple[fitz.Document, fitz.Page]:
    """Underscores below the minimum run threshold — should NOT be detected."""
    doc, page = _blank_page()
    page.insert_text((72, 100), "_" * count, fontsize=12, color=(0, 0, 0))
    return doc, page


def _page_with_hline() -> tuple[fitz.Document, fitz.Page]:
    doc, page = _blank_page()
    page.draw_line(fitz.Point(72, 200), fitz.Point(250, 200),
                   color=(0, 0, 0), width=1)
    return doc, page


def _page_with_short_hline() -> tuple[fitz.Document, fitz.Page]:
    """Line shorter than _MIN_LINE_WIDTH_PT — should NOT be detected."""
    doc, page = _blank_page()
    page.draw_line(fitz.Point(72, 200), fitz.Point(90, 200),
                   color=(0, 0, 0), width=1)
    return doc, page


def _page_with_empty_rect() -> tuple[fitz.Document, fitz.Page]:
    doc, page = _blank_page()
    # 178 × 20 = 3560 pt² — inside [400, 50000] range
    page.draw_rect(fitz.Rect(72, 250, 250, 270), color=(0, 0, 0), fill=None)
    return doc, page


def _page_with_filled_rect() -> tuple[fitz.Document, fitz.Page]:
    """Solid filled rectangle — should NOT be detected as a field."""
    doc, page = _blank_page()
    page.draw_rect(fitz.Rect(72, 250, 250, 270), color=(0, 0, 0), fill=(0, 0, 0))
    return doc, page


# ---------------------------------------------------------------------------
# Underscore detection
# ---------------------------------------------------------------------------

class TestUnderscoreDetection:
    def test_detects_underscore_span(self):
        doc, page = _page_with_underscores(8)
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) >= 1

    def test_detected_field_is_text_type(self):
        doc, page = _page_with_underscores(8)
        fields = FieldDetector().detect(page)
        doc.close()
        assert any(f.field_type == "text" for f in fields)

    def test_detected_field_has_correct_page(self):
        doc, page = _page_with_underscores(8)
        fields = FieldDetector().detect(page)
        doc.close()
        assert all(f.page_num == 0 for f in fields)

    def test_short_underscores_not_detected(self):
        """Fewer underscores than _MIN_UNDERSCORE_RUN should be ignored."""
        doc, page = _page_with_short_underscores(_MIN_UNDERSCORE_RUN - 1)
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) == 0

    def test_exact_minimum_underscores_detected(self):
        doc, page = _page_with_underscores(_MIN_UNDERSCORE_RUN)
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) >= 1

    def test_blank_page_returns_empty(self):
        doc, page = _blank_page()
        fields = FieldDetector().detect(page)
        doc.close()
        assert fields == []


# ---------------------------------------------------------------------------
# Drawing detection
# ---------------------------------------------------------------------------

class TestDrawingDetection:
    def test_detects_horizontal_line(self):
        doc, page = _page_with_hline()
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) >= 1

    def test_short_line_not_detected(self):
        doc, page = _page_with_short_hline()
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) == 0

    def test_detects_empty_rect(self):
        doc, page = _page_with_empty_rect()
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) >= 1

    def test_filled_rect_not_detected(self):
        doc, page = _page_with_filled_rect()
        fields = FieldDetector().detect(page)
        doc.close()
        assert len(fields) == 0


# ---------------------------------------------------------------------------
# Field naming and deduplication
# ---------------------------------------------------------------------------

class TestDetectorNamingAndDedup:
    def test_fields_have_unique_names(self):
        doc, page = _page_with_underscores(8)
        # Add a second underscore span at a different position
        page.insert_text((72, 150), "________", fontsize=12, color=(0, 0, 0))
        fields = FieldDetector().detect(page)
        doc.close()
        names = [f.name for f in fields]
        assert len(names) == len(set(names))

    def test_names_follow_field_n_pattern(self):
        doc, page = _page_with_underscores(8)
        fields = FieldDetector().detect(page)
        doc.close()
        for f in fields:
            assert f.name.startswith("field_")

    def test_overlapping_detections_deduplicated(self):
        """Underscore text on top of a drawn line — should not produce two fields
        at the same location."""
        doc, page = _blank_page()
        page.insert_text((72, 200), "________", fontsize=12, color=(0, 0, 0))
        page.draw_line(fitz.Point(72, 200), fitz.Point(250, 200),
                       color=(0, 0, 0), width=1)
        fields = FieldDetector().detect(page)
        doc.close()
        # Centroids within 10 pt of each other should be merged
        for i, a in enumerate(fields):
            for b in fields[i + 1:]:
                cx_a, cy_a = (a.x0 + a.x1) / 2, (a.y0 + a.y1) / 2
                cx_b, cy_b = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
                assert not (abs(cx_a - cx_b) < 10 and abs(cy_a - cy_b) < 10), \
                    f"Duplicate fields at ({cx_a:.1f},{cy_a:.1f}) and ({cx_b:.1f},{cy_b:.1f})"


# ---------------------------------------------------------------------------
# Coordinate sanity
# ---------------------------------------------------------------------------

class TestDetectorCoordinates:
    def test_rect_x1_greater_than_x0(self):
        doc, page = _page_with_underscores(8)
        fields = FieldDetector().detect(page)
        doc.close()
        for f in fields:
            assert f.x1 > f.x0, f"x1 <= x0 for field {f.name}"

    def test_rect_y1_greater_than_y0(self):
        doc, page = _page_with_underscores(8)
        fields = FieldDetector().detect(page)
        doc.close()
        for f in fields:
            assert f.y1 > f.y0, f"y1 <= y0 for field {f.name}"

    def test_coords_within_page_bounds(self):
        doc, page = _page_with_underscores(8)
        w, h = page.rect.width, page.rect.height
        fields = FieldDetector().detect(page)
        doc.close()
        for f in fields:
            assert f.x0 >= 0 and f.x1 <= w + 1, f"x out of bounds: {f}"
            assert f.y0 >= 0 and f.y1 <= h + 1, f"y out of bounds: {f}"
