"""Tests for core.pdf_processor.PDFProcessor."""
import io
import os
import tempfile

import fitz
import pytest
from PIL import Image

from core.pdf_processor import PDFProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_temp_pdf(pages: int = 1) -> str:
    """Create a real temp PDF file on disk and return its path."""
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_name = tmp.name
    tmp.close()  # close before writing on Windows
    doc.save(tmp_name)
    doc.close()
    return tmp_name


# ---------------------------------------------------------------------------
# Unloaded state
# ---------------------------------------------------------------------------

class TestPDFProcessorUnloaded:
    def test_is_loaded_false_initially(self):
        p = PDFProcessor()
        assert p.is_loaded is False

    def test_page_count_raises_when_unloaded(self):
        p = PDFProcessor()
        with pytest.raises(RuntimeError, match="No PDF loaded"):
            _ = p.page_count

    def test_render_page_raises_when_unloaded(self):
        p = PDFProcessor()
        with pytest.raises(RuntimeError, match="No PDF loaded"):
            p.render_page(0)

    def test_page_size_raises_when_unloaded(self):
        p = PDFProcessor()
        with pytest.raises(RuntimeError, match="No PDF loaded"):
            p.page_size_pt(0)

    def test_get_raw_page_raises_when_unloaded(self):
        p = PDFProcessor()
        with pytest.raises(RuntimeError, match="No PDF loaded"):
            p.get_raw_page(0)

    def test_path_empty_when_unloaded(self):
        p = PDFProcessor()
        assert p.path == ""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

class TestPDFProcessorLoading:
    def test_load_sets_is_loaded(self, tmp_path):
        pdf_path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()

        p = PDFProcessor()
        p.load(pdf_path)
        assert p.is_loaded is True
        assert p.path == pdf_path
        p.close()

    def test_load_nonexistent_file_raises(self):
        p = PDFProcessor()
        with pytest.raises(Exception):
            p.load("/nonexistent/path/file.pdf")

    def test_load_replaces_existing_doc(self, tmp_path):
        pdf1 = str(tmp_path / "a.pdf")
        pdf2 = str(tmp_path / "b.pdf")
        for path in (pdf1, pdf2):
            doc = fitz.open()
            doc.new_page()
            doc.save(path)
            doc.close()

        p = PDFProcessor()
        p.load(pdf1)
        p.load(pdf2)  # should not raise; replaces the first
        assert p.path == pdf2
        p.close()

    def test_close_resets_state(self, tmp_path):
        pdf_path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()

        p = PDFProcessor()
        p.load(pdf_path)
        p.close()
        assert p.is_loaded is False
        assert p.path == ""


# ---------------------------------------------------------------------------
# Page count & size
# ---------------------------------------------------------------------------

class TestPDFProcessorPages:
    def setup_method(self):
        self.p = PDFProcessor()
        self._paths: list[str] = []

    def teardown_method(self):
        self.p.close()
        for path in self._paths:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _load(self, pages: int = 1) -> str:
        path = _write_temp_pdf(pages)
        self._paths.append(path)
        self.p.load(path)
        return path

    def test_single_page_count(self):
        self._load(1)
        assert self.p.page_count == 1

    def test_multi_page_count(self):
        self._load(5)
        assert self.p.page_count == 5

    def test_a4_page_size(self):
        self._load(1)
        w, h = self.p.page_size_pt(0)
        assert w == pytest.approx(595.0)
        assert h == pytest.approx(842.0)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestPDFProcessorRender:
    def setup_method(self):
        self.p = PDFProcessor()
        self._paths: list[str] = []

    def teardown_method(self):
        self.p.close()
        for path in self._paths:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _load(self, pages: int = 1):
        path = _write_temp_pdf(pages)
        self._paths.append(path)
        self.p.load(path)

    def test_render_returns_pil_image(self):
        self._load()
        img = self.p.render_page(0)
        assert isinstance(img, Image.Image)

    def test_render_mode_is_rgb(self):
        self._load()
        img = self.p.render_page(0)
        assert img.mode == "RGB"

    def test_render_zoom_affects_size(self):
        self._load()
        img1 = self.p.render_page(0, zoom=1.0)
        img2 = self.p.render_page(0, zoom=2.0)
        assert img2.width == pytest.approx(img1.width * 2, abs=2)
        assert img2.height == pytest.approx(img1.height * 2, abs=2)

    def test_render_default_zoom_is_1_5(self):
        self._load()
        img_default = self.p.render_page(0)
        img_1 = self.p.render_page(0, zoom=1.0)
        assert img_default.width == pytest.approx(img_1.width * 1.5, abs=2)

    def test_get_raw_page_returns_fitz_page(self):
        self._load()
        page = self.p.get_raw_page(0)
        assert isinstance(page, fitz.Page)
