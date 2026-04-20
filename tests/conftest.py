"""Shared fixtures for all tests.

Provides:
- A minimal in-memory fitz.Document with one blank page (A4).
- A fitz.Document whose first page contains underscore text spans and
  a horizontal line drawing — used by FieldDetector tests.
- A temporary output path helper.
"""
from __future__ import annotations

import io
import os
import tempfile

import fitz
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_blank_doc(pages: int = 1) -> fitz.Document:
    """Return an in-memory A4 document with *pages* blank pages."""
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    return doc


def _make_form_doc() -> fitz.Document:
    """Return a one-page A4 document that contains:
    - A text span of underscores ('________') that the detector should find.
    - A horizontal black line (30 pt wide, 1 pt tall) that the detector should find.
    - A small empty rectangle that the detector should find.
    - A normal word 'Name:' that should NOT be detected.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Insert underscore text
    page.insert_text((72, 100), "Name: ________", fontsize=12, color=(0, 0, 0))

    # Draw a horizontal line at y=200
    page.draw_line(fitz.Point(72, 200), fitz.Point(250, 200), color=(0, 0, 0), width=1)

    # Draw an empty rectangle at (72, 250, 250, 270)
    page.draw_rect(fitz.Rect(72, 250, 250, 270), color=(0, 0, 0), fill=None)

    return doc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blank_doc():
    doc = _make_blank_doc()
    yield doc
    doc.close()


@pytest.fixture
def blank_doc_multipage():
    doc = _make_blank_doc(pages=3)
    yield doc
    doc.close()


@pytest.fixture
def form_doc():
    doc = _make_form_doc()
    yield doc
    doc.close()


@pytest.fixture
def tmp_pdf_path(tmp_path):
    """Return a Path pointing to a not-yet-existing PDF file in a temp dir."""
    return str(tmp_path / "output.pdf")
