"""Tests for core.pdf_builder.PDFBuilder."""
import os

import fitz
import pytest

from core.pdf_builder import PDFBuilder
from models.form_field import FormField


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(pages: int = 1) -> fitz.Document:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    return doc


def _field(name: str, page_num: int = 0, field_type: str = "text") -> FormField:
    return FormField(
        field_type=field_type,
        x0=72, y0=100, x1=250, y1=120,
        name=name,
        page_num=page_num,
    )


def _widget_names_on_page(page: fitz.Page) -> list[str]:
    return [w.field_name for w in page.widgets()]


# ---------------------------------------------------------------------------
# apply_fields
# ---------------------------------------------------------------------------

class TestApplyFields:
    def test_single_text_field_added(self):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("name_field")])
        names = _widget_names_on_page(doc[0])
        assert "name_field" in names
        doc.close()

    def test_multiple_fields_added(self):
        doc = _make_doc()
        fields = [
            _field("f1"),
            FormField(field_type="text", x0=72, y0=140, x1=250, y1=160,
                      name="f2", page_num=0),
        ]
        builder = PDFBuilder(doc)
        builder.apply_fields(fields)
        names = _widget_names_on_page(doc[0])
        assert "f1" in names
        assert "f2" in names
        doc.close()

    def test_checkbox_field_added(self):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("cb", field_type="checkbox")])
        names = _widget_names_on_page(doc[0])
        assert "cb" in names
        doc.close()

    def test_dropdown_field_added(self):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("dd", field_type="dropdown")])
        names = _widget_names_on_page(doc[0])
        assert "dd" in names
        doc.close()

    def test_radio_field_added(self):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("rb", field_type="radio")])
        names = _widget_names_on_page(doc[0])
        assert "rb" in names
        doc.close()

    def test_fields_on_different_pages(self):
        doc = _make_doc(pages=3)
        fields = [
            _field("page0_field", page_num=0),
            _field("page2_field", page_num=2),
        ]
        builder = PDFBuilder(doc)
        builder.apply_fields(fields)
        assert "page0_field" in _widget_names_on_page(doc[0])
        assert "page2_field" in _widget_names_on_page(doc[2])
        assert _widget_names_on_page(doc[1]) == []
        doc.close()

    def test_out_of_range_page_skipped(self):
        """Fields referencing non-existent pages should be silently skipped."""
        doc = _make_doc(pages=1)
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("ghost", page_num=99)])
        assert _widget_names_on_page(doc[0]) == []
        doc.close()

    def test_empty_fields_list_no_error(self):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([])   # should not raise
        doc.close()

    def test_duplicate_name_replaced(self):
        """Applying a field with a name that already exists should replace, not duplicate."""
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("dup")])
        builder.apply_fields([_field("dup")])
        names = _widget_names_on_page(doc[0])
        assert names.count("dup") == 1
        doc.close()

    def test_default_value_stored(self):
        doc = _make_doc()
        f = FormField(field_type="text", x0=72, y0=100, x1=250, y1=120,
                      name="prefilled", page_num=0, default_value="Jane Doe")
        builder = PDFBuilder(doc)
        builder.apply_fields([f])
        widgets = list(doc[0].widgets())
        match = next((w for w in widgets if w.field_name == "prefilled"), None)
        assert match is not None
        assert match.field_value == "Jane Doe"
        doc.close()


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestPDFBuilderSave:
    def test_save_creates_file(self, tmp_path):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("f1")])
        out = str(tmp_path / "out.pdf")
        builder.save(out)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0
        doc.close()

    def test_saved_file_is_valid_pdf(self, tmp_path):
        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("f1")])
        out = str(tmp_path / "out.pdf")
        builder.save(out)
        # Re-open and verify the widget survived the round-trip
        doc2 = fitz.open(out)
        names = _widget_names_on_page(doc2[0])
        assert "f1" in names
        doc2.close()
        doc.close()

    def test_saved_file_contains_all_field_types(self, tmp_path):
        doc = _make_doc()
        fields = [
            FormField(field_type="text",     x0=72, y0=100, x1=250, y1=120, name="txt", page_num=0),
            FormField(field_type="checkbox", x0=72, y0=130, x1=92,  y1=150, name="chk", page_num=0),
            FormField(field_type="dropdown", x0=72, y0=160, x1=250, y1=180, name="ddl", page_num=0),
        ]
        builder = PDFBuilder(doc)
        builder.apply_fields(fields)
        out = str(tmp_path / "out.pdf")
        builder.save(out)

        doc2 = fitz.open(out)
        names = _widget_names_on_page(doc2[0])
        doc2.close()
        doc.close()
        assert "txt" in names
        assert "chk" in names
        assert "ddl" in names

    def test_save_overwrites_existing_file(self, tmp_path):
        out = str(tmp_path / "out.pdf")
        # Write a dummy file first
        with open(out, "wb") as fp:
            fp.write(b"dummy")

        doc = _make_doc()
        builder = PDFBuilder(doc)
        builder.apply_fields([_field("f1")])
        builder.save(out)
        doc.close()

        doc2 = fitz.open(out)
        names = _widget_names_on_page(doc2[0])
        doc2.close()
        assert "f1" in names
