from __future__ import annotations

import fitz  # PyMuPDF
from PIL import Image


class PDFProcessor:
    """Handles loading a PDF and rendering its pages to PIL Images."""

    def __init__(self):
        self._doc: fitz.Document | None = None
        self._path: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        """Open a PDF file.  Raises FileNotFoundError / fitz.FileDataError on bad input."""
        if self._doc is not None:
            self._doc.close()
        self._doc = fitz.open(path)
        self._path = path

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None
            self._path = ""

    @property
    def is_loaded(self) -> bool:
        return self._doc is not None

    @property
    def page_count(self) -> int:
        self._require_loaded()
        return self._doc.page_count

    @property
    def path(self) -> str:
        return self._path

    def page_size_pt(self, page_num: int) -> tuple[float, float]:
        """Return (width, height) in PDF points for the given page (0-based)."""
        self._require_loaded()
        rect = self._doc[page_num].rect
        return (rect.width, rect.height)

    def render_page(self, page_num: int, zoom: float = 1.5) -> Image.Image:
        """Render a PDF page to a PIL Image.

        Args:
            page_num: 0-based page index.
            zoom:     Scaling factor (1.5 → 108 DPI equivalent for a 72-DPI PDF).

        Returns:
            RGB PIL Image.
        """
        self._require_loaded()
        page = self._doc[page_num]
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    def get_raw_page(self, page_num: int) -> fitz.Page:
        """Return the raw fitz.Page for advanced operations (e.g. detection)."""
        self._require_loaded()
        return self._doc[page_num]

    def get_document(self) -> fitz.Document:
        """Return the underlying fitz.Document."""
        self._require_loaded()
        return self._doc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_loaded(self) -> None:
        if self._doc is None:
            raise RuntimeError("No PDF loaded. Call load() first.")
