"""Tests for models.form_field.FormField."""
import pytest
from models.form_field import FormField, FIELD_TYPES


# ---------------------------------------------------------------------------
# Construction — valid cases
# ---------------------------------------------------------------------------

class TestFormFieldValid:
    def test_text_field_created(self):
        f = FormField(field_type="text", x0=10, y0=20, x1=110, y1=40,
                      name="my_field", page_num=0)
        assert f.field_type == "text"
        assert f.name == "my_field"
        assert f.page_num == 0
        assert f.default_value == ""
        assert f.label == ""

    def test_all_field_types_accepted(self):
        for ft in FIELD_TYPES:
            f = FormField(field_type=ft, x0=0, y0=0, x1=50, y1=20,
                          name="f", page_num=0)
            assert f.field_type == ft

    def test_default_value_stored(self):
        f = FormField(field_type="text", x0=0, y0=0, x1=50, y1=20,
                      name="f", page_num=0, default_value="hello")
        assert f.default_value == "hello"

    def test_label_stored(self):
        f = FormField(field_type="text", x0=0, y0=0, x1=50, y1=20,
                      name="f", page_num=0, label="First Name")
        assert f.label == "First Name"

    def test_pdf_rect_tuple(self):
        f = FormField(field_type="text", x0=10, y0=20, x1=110, y1=40,
                      name="f", page_num=0)
        assert f.pdf_rect_tuple() == (10, 20, 110, 40)

    def test_multipage_page_num(self):
        f = FormField(field_type="checkbox", x0=0, y0=0, x1=20, y1=20,
                      name="cb", page_num=5)
        assert f.page_num == 5

    def test_float_coordinates(self):
        f = FormField(field_type="text", x0=10.5, y0=20.75, x1=110.25, y1=40.1,
                      name="f", page_num=0)
        assert f.x0 == pytest.approx(10.5)
        assert f.y1 == pytest.approx(40.1)


# ---------------------------------------------------------------------------
# Validation — invalid cases
# ---------------------------------------------------------------------------

class TestFormFieldInvalid:
    def test_invalid_field_type_raises(self):
        with pytest.raises(ValueError, match="field_type must be one of"):
            FormField(field_type="signature", x0=0, y0=0, x1=50, y1=20,
                      name="f", page_num=0)

    def test_empty_field_type_raises(self):
        with pytest.raises(ValueError):
            FormField(field_type="", x0=0, y0=0, x1=50, y1=20,
                      name="f", page_num=0)

    def test_x1_equals_x0_raises(self):
        with pytest.raises(ValueError, match="Invalid rect"):
            FormField(field_type="text", x0=50, y0=0, x1=50, y1=20,
                      name="f", page_num=0)

    def test_x1_less_than_x0_raises(self):
        with pytest.raises(ValueError, match="Invalid rect"):
            FormField(field_type="text", x0=100, y0=0, x1=50, y1=20,
                      name="f", page_num=0)

    def test_y1_equals_y0_raises(self):
        with pytest.raises(ValueError, match="Invalid rect"):
            FormField(field_type="text", x0=0, y0=20, x1=50, y1=20,
                      name="f", page_num=0)

    def test_y1_less_than_y0_raises(self):
        with pytest.raises(ValueError, match="Invalid rect"):
            FormField(field_type="text", x0=0, y0=50, x1=50, y1=20,
                      name="f", page_num=0)
